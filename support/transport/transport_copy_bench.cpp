#include "transport_abi.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <span>
#include <string_view>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

#if defined(__ARM_NEON)
#include <arm_neon.h>
#endif

namespace {

using diablo::mister::transport::FRAME_PIXEL_BYTES;
using diablo::mister::transport::FrameOffset;
using diablo::mister::transport::SHARED_BYTES;

std::uint32_t CrcTableValue(std::uint32_t value)
{
	for (unsigned bit = 0; bit < 8; ++bit)
		value = (value >> 1U) ^ (0xEDB88320U & static_cast<std::uint32_t>(-
		    static_cast<std::int32_t>(value & 1U)));
	return value;
}

std::uint32_t Crc32(const std::uint8_t *source)
{
	static std::uint32_t table[256] = {};
	static bool initialized = false;
	if (!initialized) {
		for (std::uint32_t index = 0; index < 256; ++index)
			table[index] = CrcTableValue(index);
		initialized = true;
	}
	std::uint32_t crc = 0xFFFFFFFFU;
	for (std::size_t offset = 0; offset < FRAME_PIXEL_BYTES; ++offset)
		crc = table[(crc ^ source[offset]) & 0xFFU] ^ (crc >> 8U);
	return ~crc;
}

void CopyScalar64(std::uint8_t *destination, const std::uint8_t *source)
{
	std::size_t offset = 0;
	for (; offset + sizeof(std::uint64_t) <= FRAME_PIXEL_BYTES;
	     offset += sizeof(std::uint64_t)) {
		std::uint64_t value;
		std::memcpy(&value, source + offset, sizeof(value));
		std::memcpy(destination + offset, &value, sizeof(value));
	}
	if (offset < FRAME_PIXEL_BYTES)
		std::memcpy(destination + offset, source + offset, FRAME_PIXEL_BYTES - offset);
}

void CopyNeon(std::uint8_t *destination, const std::uint8_t *source)
{
#if defined(__ARM_NEON)
	std::size_t offset = 0;
	for (; offset + 16U <= FRAME_PIXEL_BYTES; offset += 16U)
		vst1q_u8(destination + offset, vld1q_u8(source + offset));
	if (offset < FRAME_PIXEL_BYTES)
		std::memcpy(destination + offset, source + offset, FRAME_PIXEL_BYTES - offset);
#else
	std::memcpy(destination, source, FRAME_PIXEL_BYTES);
#endif
}

int Run(std::string_view mode, std::uint8_t *destination,
        const std::uint8_t *source, unsigned iterations)
{
	volatile std::uint32_t checksum = 0;
	const auto start = std::chrono::steady_clock::now();
	for (unsigned iteration = 0; iteration < iterations; ++iteration) {
		if (mode == "memcpy")
			std::memcpy(destination, source, FRAME_PIXEL_BYTES);
		else if (mode == "rows")
			for (std::uint32_t row = 0; row < 480; ++row)
				std::memcpy(destination + row * 640, source + row * 640, 640);
		else if (mode == "scalar64")
			CopyScalar64(destination, source);
		else if (mode == "neon")
			CopyNeon(destination, source);
		else if (mode == "crc")
			checksum ^= Crc32(source);
		else
			return 2;
		__sync_synchronize();
	}
	const auto elapsed = std::chrono::duration<double>(
	    std::chrono::steady_clock::now() - start).count();
	const double megabytes = static_cast<double>(FRAME_PIXEL_BYTES) * iterations / (1024.0 * 1024.0);
	std::printf("mode=%.*s iterations=%u seconds=%.6f MiB/s=%.2f\n",
            static_cast<int>(mode.size()), mode.data(), iterations, elapsed,
            megabytes / elapsed);
	if (checksum == 0xFFFFFFFFU)
		std::fputs("checksum sentinel\n", stdout);
	return 0;
}

} // namespace

int main(int argc, char **argv)
{
	if (argc < 3) {
		std::fprintf(stderr, "usage: %s <memcpy|rows|scalar64|neon|crc> <iterations> [cached]\n", argv[0]);
		return 2;
	}
	char *end = nullptr;
	const auto iterations = std::strtoul(argv[2], &end, 0);
	if (end == argv[2] || *end != '\0' || iterations == 0 || iterations > 10000)
		return 2;
	const bool cached = argc >= 4 && std::string_view(argv[3]) == "cached";
	const int flags = O_RDWR | O_CLOEXEC | (cached ? 0 : O_SYNC);
	const int fd = ::open("/dev/mem", flags);
	if (fd < 0) {
		std::perror("open /dev/mem");
		return 1;
	}
	void *mapping = ::mmap(nullptr, SHARED_BYTES, PROT_READ | PROT_WRITE,
	                       MAP_SHARED, fd, 0x3fe00000);
	if (mapping == MAP_FAILED) {
		std::perror("mmap /dev/mem");
		::close(fd);
		return 1;
	}
	std::vector<std::uint8_t> source(FRAME_PIXEL_BYTES);
	for (std::size_t index = 0; index < source.size(); ++index)
		source[index] = static_cast<std::uint8_t>(index * 17U + 3U);
	auto *destination = static_cast<std::uint8_t *>(mapping) + FrameOffset(0);
	const int result = Run(argv[1], destination, source.data(), static_cast<unsigned>(iterations));
	(void)::msync(mapping, SHARED_BYTES, MS_SYNC);
	::munmap(mapping, SHARED_BYTES);
	::close(fd);
	return result;
}
