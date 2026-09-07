// Inject deterministic ARM-visible input records into a MiSTer transport ring.
// This validates the ARM input-to-SDL bridge without pretending to be a
// physical keyboard, mouse or controller. Production input is still written
// by rtl/diablo_input_capture.sv.
#include "transport_abi.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <thread>
#include <sys/mman.h>
#include <unistd.h>

namespace {

using namespace diablo::mister::transport;

constexpr std::uint64_t SharedPhysical = 0x3fe00000ULL;

std::uint64_t ParsePhysical()
{
	const char *value = std::getenv("DIABLO_MISTER_SHARED_PHYS");
	if (value == nullptr || *value == '\0') return SharedPhysical;
	char *end = nullptr;
	const auto parsed = std::strtoull(value, &end, 0);
	if (end == value || *end != '\0' || parsed == 0) return SharedPhysical;
	return parsed;
}

bool Ready(const Header &header)
{
        return std::memcmp(header.magic.data(), MAGIC.data(), MAGIC.size()) == 0
	    && header.session_epoch != 0
	    && std::atomic_ref<const std::uint32_t>(header.arm_state).load(std::memory_order_acquire)
	        == static_cast<std::uint32_t>(ComponentState::Ready);
}

bool WriteEvent(Header &header, std::span<std::byte> memory, std::uint32_t type,
                std::uint32_t code, std::int32_t value0, std::int32_t value1,
                std::uint64_t buttons)
{
	std::atomic_ref<std::uint32_t> producer(header.input.producer_sequence);
	const std::uint32_t write = producer.load(std::memory_order_relaxed);
	const std::uint32_t read = std::atomic_ref<std::uint32_t>(header.input.consumer_sequence)
	                               .load(std::memory_order_acquire);
	if (write - read >= INPUT_CAPACITY) return false;
	InputEvent event {
		.sequence = write,
		.timestamp = write,
		.type = type,
		.code = code,
		.value0 = value0,
		.value1 = value1,
		.buttons = buttons,
	};
	const std::size_t offset = INPUT_REGION_OFFSET
	                         + static_cast<std::size_t>(write & (INPUT_CAPACITY - 1U))
	                               * INPUT_RECORD_BYTES;
	std::memcpy(memory.data() + offset, &event, sizeof(event));
	std::atomic_thread_fence(std::memory_order_release);
	producer.store(write + 1U, std::memory_order_release);
	return true;
}

} // namespace

int main(int argc, char **argv)
{
	const bool overflow_test = argc > 1 && std::strcmp(argv[1], "--overflow-test") == 0;
	const long page_size = ::sysconf(_SC_PAGESIZE);
	if (page_size <= 0) return 2;
	const std::uint64_t physical = ParsePhysical();
	const std::uint64_t page_mask = static_cast<std::uint64_t>(page_size - 1);
	const std::uint64_t page_base = physical & ~page_mask;
	const std::size_t offset = static_cast<std::size_t>(physical - page_base);
	const std::size_t mapped_bytes = offset + SHARED_BYTES;
	const int fd = ::open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (fd < 0) return 3;
	void *mapping = ::mmap(nullptr, mapped_bytes, PROT_READ | PROT_WRITE,
	                       MAP_SHARED, fd, static_cast<off_t>(page_base));
	if (mapping == MAP_FAILED) {
		::close(fd);
		return 4;
	}
	std::span<std::byte> memory(static_cast<std::byte *>(mapping) + offset, SHARED_BYTES);
	auto *header = reinterpret_cast<Header *>(memory.data());
	for (unsigned attempt = 0; attempt < 5000 && !Ready(*header); ++attempt)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	if (!Ready(*header)) {
		::munmap(mapping, mapped_bytes);
		::close(fd);
		return 5;
	}

	if (overflow_test) {
		// This is a synthetic validation fixture: production writes the producer
		// cursor from rtl/diablo_input_capture.sv. Advancing it beyond the bounded
		// ring capacity forces the same occupied>capacity path that a stalled ARM
		// consumer would see, so the SDL adapter's snapshot recovery is exercised
		// without pretending that a physical peripheral generated the overflow.
		std::atomic_ref<std::uint32_t> producer(header->input.producer_sequence);
		const std::uint32_t consumer = std::atomic_ref<std::uint32_t>(
			header->input.consumer_sequence).load(std::memory_order_acquire);
		const std::uint32_t injected = consumer + INPUT_CAPACITY + 1U;
		std::atomic_thread_fence(std::memory_order_release);
		producer.store(injected, std::memory_order_release);
		std::fprintf(stderr,
		             "input overflow injected epoch=0x%08x producer=%u consumer=%u occupied=%u\n",
		             header->session_epoch, injected, consumer, injected - consumer);
		std::this_thread::sleep_for(std::chrono::milliseconds(500));
		::munmap(mapping, mapped_bytes);
		::close(fd);
		return 0;
	}

	const std::uint64_t joystick = (1ULL << 4U) | (1ULL << 7U);
	const auto emit = [&](std::uint32_t type, std::uint32_t code,
	                     std::int32_t value0, std::int32_t value1,
	                     std::uint64_t buttons) {
		if (!WriteEvent(*header, memory, type, code, value0, value1, buttons))
			std::fprintf(stderr, "input injector ring full\n");
		__sync_synchronize();
		std::this_thread::sleep_for(std::chrono::milliseconds(40));
	};

	emit(INPUT_EVENT_KEYBOARD, 0x01cU, 1, 0, 0);
	emit(INPUT_EVENT_KEYBOARD, 0x01cU, 0, 0, 0);
	emit(INPUT_EVENT_MOUSE, 0x100U, 12, -7, 0);
	emit(INPUT_EVENT_MOUSE, 0x000U, 0, 0, 0);
	emit(INPUT_EVENT_MOUSE, 0x001U, 0, 0, 0);
	emit(INPUT_EVENT_MOUSE, 0x000U, 0, 0, 0);
	emit(INPUT_EVENT_MOUSE, 0xff00U, 0, 0, 0);
	emit(INPUT_EVENT_JOYSTICK, 0, static_cast<std::int32_t>(0x007f),
	     static_cast<std::int32_t>(0xff80), joystick);
	emit(INPUT_EVENT_JOYSTICK, 0, 0, 0, 0);

	::munmap(mapping, mapped_bytes);
	::close(fd);
	return 0;
}
