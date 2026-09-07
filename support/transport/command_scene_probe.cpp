// Controlled ARM command-scene publisher for the integrated FPGA consumer.
// It writes a small deterministic indexed scene into slot zero, publishes the
// bounded FillRect/CopyRect/End stream, and compares shared DDR with the
// independent software renderer before exposing the frame to scanout.
#include "mister_command_renderer.hpp"
#include "mister_command_transport.hpp"
#include "mister_transport_runtime.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>

namespace {
using namespace diablo::mister::command;
using namespace diablo::mister::transport;

constexpr std::uint64_t kFence = 0x1122334455667788ULL;

int Fail(const char *message)
{
	std::fprintf(stderr, "command scene probe failed: %s\n", message);
	return 1;
}

} // namespace

int main()
{
	auto opened = TransportRuntime::Open();
	if (!opened.has_value()) return Fail("runtime mapping did not open");
	TransportRuntime runtime = std::move(*opened);
	// A live core reload can leave the control reader in its bounded retry
	// window while ARM publishes the new page. Give the controlled probe the
	// same startup margin as a real engine launch instead of turning that
	// expected hand-off latency into a false failure.
	if (!runtime.WaitForFpgaReady(10000)) return Fail("FPGA did not attach");

	TransportSession &session = runtime.session();
	const std::uint32_t epoch = session.epoch();
	AbiView view = session.view();
	auto frame = view.ArmBeginFrameFast(0, epoch);
	if (!frame.has_value()) return Fail("slot zero was not free");
	const FrameSlot &descriptor = *frame.value();
	auto target = view.memory().subspan(descriptor.pixel_offset, FRAME_PIXEL_BYTES);
	std::fill(target.begin(), target.end(), std::byte { 0 });

	Buffer commands;
	if (!commands.FillRect(0, 0, 80, 60, 2)
	    || !commands.FillRect(10, 8, 24, 18, 0x3c)
	    || !commands.CopyRect(100, 8, 24, 18, 10, 8)
	    || !commands.CopyRect(18, 30, 32, 24, 10, 8)
	    || !commands.End(kFence))
		return Fail("could not build command scene");

	std::vector<std::uint8_t> expected(FRAME_PIXEL_BYTES, 0);
	SoftwareRenderer reference(expected, FRAME_WIDTH, FRAME_WIDTH, FRAME_HEIGHT);
	if (!reference.Execute(commands.records())) return Fail("software reference rejected scene");

	Publisher publisher(view, epoch);
	auto published = publisher.Publish(commands.records(), {});
	if (!published.has_value() || !runtime.Flush()) return Fail("command batch publication failed");

	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	std::atomic_ref<std::uint64_t> completed_fence(view.header().last_completed_fence);
	std::atomic_ref<std::uint32_t> record_consumer(view.header().command_records.consumer_sequence);
	while (completed_fence.load(std::memory_order_acquire) != kFence
	       || record_consumer.load(std::memory_order_acquire) < commands.size()) {
		if (std::chrono::steady_clock::now() >= deadline) return Fail("FPGA did not complete command fence");
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}

	if (std::memcmp(target.data(), expected.data(), FRAME_PIXEL_BYTES) != 0)
		return Fail("FPGA command target differs from software reference");

	auto palette = view.memory().subspan(descriptor.palette_offset, PALETTE_BYTES);
	for (std::size_t index = 0; index < 256; ++index) {
		palette[index * 3 + 0] = static_cast<std::byte>(index);
		palette[index * 3 + 1] = static_cast<std::byte>(255U - index);
		palette[index * 3 + 2] = static_cast<std::byte>((index * 3U) & 0xffU);
	}
	if (!view.ArmPublishFrameFast(0, epoch, 1, 1, kFence, 0, FRAME_CHECKSUM_ABSENT) || !runtime.Flush())
		return Fail("command target frame publication failed");

	for (unsigned attempt = 0; attempt < 200; ++attempt) {
		if (view.header().frames[0].state == static_cast<std::uint32_t>(FrameState::FpgaDisplaying))
			break;
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	std::printf("command scene probe passed: epoch=0x%08x records=%u fence=0x%016llx frame_state=%u last_presented=%llu\n",
	            epoch, commands.size(), static_cast<unsigned long long>(kFence),
	            view.header().frames[0].state,
	            static_cast<unsigned long long>(view.header().last_presented_frame_id));
	return 0;
}
