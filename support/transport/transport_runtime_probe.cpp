// File-backed runtime probe for the ARM transport mapping lifecycle.
// The same code path accepts an explicitly admitted /dev/mem physical base
// through DIABLO_MISTER_SHARED_PHYS on the target.
#include "mister_transport_runtime.hpp"

#include <array>
#include <cstdio>
#include <cstdint>
#include <utility>
#include <vector>

namespace {
using namespace diablo::mister::transport;

int Fail(RuntimeError error)
{
	std::fprintf(stderr, "transport runtime probe failed: error=%u\n",
	             static_cast<unsigned>(error));
	return 1;
}
} // namespace

int main()
{
	auto runtime = TransportRuntime::Open();
	if (!runtime.has_value()) return Fail(runtime.error());
	TransportRuntime session = std::move(*runtime);
	const std::uint32_t epoch = session.session().view().header().session_epoch;
	if (epoch == 0 || !session.session().view().Validate(epoch).has_value()) {
		std::fputs("transport runtime probe failed: attached ABI did not validate\n", stderr);
		return 1;
	}

	std::vector<std::uint8_t> pixels(static_cast<std::size_t>(FRAME_WIDTH) * FRAME_HEIGHT, 7);
	std::array<std::uint8_t, PALETTE_BYTES> palette {};
	for (std::size_t index = 0; index < palette.size(); ++index)
		palette[index] = static_cast<std::uint8_t>(index);
	auto frame = session.session().PublishIndexedFrame(pixels, FRAME_WIDTH, palette, 1);
	if (!frame.has_value() || *frame != 1 || !session.Flush()) {
		std::fputs("transport runtime probe failed: frame publication or flush\n", stderr);
		return 1;
	}
	std::printf("transport runtime probe passed: epoch=0x%08x frame=%llu state=%u\n",
	            epoch, static_cast<unsigned long long>(*frame),
	            session.session().view().header().frames[0].state);
	return 0;
}
