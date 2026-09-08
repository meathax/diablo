// SPDX-License-Identifier: GPL-2.0-or-later
#define SDL_MAIN_HANDLED

#include <SDL.h>

#include "mister_movie_frame.hpp"
#include "mister_transport_sdl.hpp"
#include "transport_abi.hpp"

#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <optional>
#include <span>
#include <string>
#include <sys/mman.h>
#include <unistd.h>
#include <utility>
#include <vector>

namespace {

using diablo::mister::sdl::Adapter;
using diablo::mister::transport::AbiView;
using diablo::mister::transport::ComponentState;
using diablo::mister::transport::FRAME_SLOTS;
using diablo::mister::transport::FrameState;
using diablo::mister::transport::Header;
using diablo::mister::transport::MAGIC;
using diablo::mister::transport::SHARED_BYTES;
using diablo::mister::movie::IndexedFrameAdapter;
using diablo::mister::movie::PrepareError;

[[noreturn]] void Fail(const char *message)
{
	std::fprintf(stderr, "cinematic transport regression failure: %s\n", message);
	std::exit(EXIT_FAILURE);
}

void Check(bool condition, const char *message)
{
	if (!condition) Fail(message);
}

void SetEnvironment(const char *name, const std::string &value)
{
	if (::setenv(name, value.c_str(), 1) != 0) Fail("setenv failed");
}

struct SharedFile {
	int fd = -1;
	void *mapping = MAP_FAILED;
	Header *header = nullptr;

	explicit SharedFile(const std::filesystem::path &path)
	{
		fd = ::open(path.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0600);
		if (fd < 0 || ::ftruncate(fd, SHARED_BYTES) != 0)
			Fail("could not create the file-backed shared aperture");
		mapping = ::mmap(nullptr, SHARED_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
		if (mapping == MAP_FAILED) Fail("could not map the file-backed shared aperture");
		header = static_cast<Header *>(mapping);
	}

	~SharedFile()
	{
		if (mapping != MAP_FAILED) ::munmap(mapping, SHARED_BYTES);
		if (fd >= 0) ::close(fd);
	}

	SharedFile(const SharedFile &) = delete;
	SharedFile &operator=(const SharedFile &) = delete;
};

void SetFpgaState(Header &header, ComponentState state)
{
	std::atomic_ref<std::uint32_t>(header.fpga_state).store(
	    static_cast<std::uint32_t>(state), std::memory_order_release);
}

struct Surface {
	SDL_Surface *value = nullptr;

	Surface() = default;
	~Surface()
	{
		if (value != nullptr) SDL_FreeSurface(value);
	}

	Surface(const Surface &) = delete;
	Surface &operator=(const Surface &) = delete;
	Surface(Surface &&other) noexcept : value(std::exchange(other.value, nullptr)) {}
	Surface &operator=(Surface &&other) noexcept
	{
		if (this != &other) {
			if (value != nullptr) SDL_FreeSurface(value);
			value = std::exchange(other.value, nullptr);
		}
		return *this;
	}
};

Surface MakeSurface(std::uint8_t pixel, std::uint8_t palette_seed)
{
	Surface result;
	result.value = SDL_CreateRGBSurfaceWithFormat(
	    0, 640, 480, 8, SDL_PIXELFORMAT_INDEX8);
	if (result.value == nullptr || result.value->format == nullptr
	    || result.value->format->palette == nullptr)
		Fail("could not create indexed cinematic surface");
	std::memset(result.value->pixels, pixel,
	            static_cast<std::size_t>(result.value->pitch) * result.value->h);
	std::array<SDL_Color, 256> palette {};
	for (std::size_t index = 0; index < palette.size(); ++index) {
		palette[index].r = static_cast<std::uint8_t>(palette_seed + index);
		palette[index].g = static_cast<std::uint8_t>(palette_seed ^ index);
		palette[index].b = static_cast<std::uint8_t>(palette_seed + 3U * index);
		palette[index].a = SDL_ALPHA_OPAQUE;
	}
	if (SDL_SetPaletteColors(result.value->format->palette, palette.data(), 0, 256) != 0)
		Fail("could not initialize cinematic palette");
	return result;
}

std::uint8_t PixelAt(SDL_Surface *surface, int x, int y)
{
	Check(surface != nullptr && surface->pixels != nullptr, "surface pixels were unavailable");
	Check(x >= 0 && x < surface->w && y >= 0 && y < surface->h,
	      "pixel coordinate was outside the surface");
	const auto *pixels = static_cast<const std::uint8_t *>(surface->pixels);
	return pixels[static_cast<std::size_t>(y) * static_cast<std::size_t>(surface->pitch)
	              + static_cast<std::size_t>(x)];
}

Surface MakeGeometrySurface(int width, int height, std::uint8_t pixel,
                            std::uint8_t black_index, bool exact_black)
{
	Surface result;
	result.value = SDL_CreateRGBSurfaceWithFormat(0, width, height, 8, SDL_PIXELFORMAT_INDEX8);
	if (result.value == nullptr || result.value->format == nullptr
	    || result.value->format->palette == nullptr)
		Fail("could not create indexed geometry surface");
	std::memset(result.value->pixels, pixel,
	            static_cast<std::size_t>(result.value->pitch) * result.value->h);
	std::array<SDL_Color, 256> palette {};
	for (std::size_t index = 0; index < palette.size(); ++index) {
		palette[index].r = static_cast<std::uint8_t>(1U + (index * 17U) % 251U);
		palette[index].g = static_cast<std::uint8_t>(1U + (index * 31U) % 251U);
		palette[index].b = static_cast<std::uint8_t>(1U + (index * 47U) % 251U);
		palette[index].a = SDL_ALPHA_OPAQUE;
	}
	if (exact_black) {
		palette[black_index] = SDL_Color {0, 0, 0, SDL_ALPHA_OPAQUE};
	}
	if (SDL_SetPaletteColors(result.value->format->palette, palette.data(), 0, 256) != 0)
		Fail("could not initialize indexed geometry palette");
	return result;
}

void RunMovieFrameGeometryChecks()
{
	const SDL_Rect expected_destination = {0, 84, 640, 312};
	const auto destination = diablo::mister::movie::ComputeDestinationRect(320, 156);
	Check(destination.x == expected_destination.x && destination.y == expected_destination.y
	          && destination.w == expected_destination.w && destination.h == expected_destination.h,
	      "320x156 cinematic geometry was not centered at 640x480");

	Surface native_source = MakeSurface(0x2AU, 0x31U);
	IndexedFrameAdapter native_adapter;
	const auto native = native_adapter.Prepare(native_source.value);
	Check(native.error == PrepareError::None && native.surface == native_source.value,
	      "native 640x480 cinematic surface did not use the fast path");
	Check(native.destination.x == 0 && native.destination.y == 0
	          && native.destination.w == 640 && native.destination.h == 480,
	      "native cinematic destination was changed");

	Surface source = MakeGeometrySurface(320, 156, 42U, 7U, true);
	IndexedFrameAdapter adapter;
	auto prepared = adapter.Prepare(source.value);
	if (prepared.error != PrepareError::None || prepared.surface == nullptr) {
		std::fprintf(stderr, "indexed movie preparation error=%d sdl=%s\n",
		             static_cast<int>(prepared.error), SDL_GetError());
		Fail("indexed movie preparation failed");
	}
	Check(prepared.surface->w == 640 && prepared.surface->h == 480,
	      "prepared indexed movie did not use the transport frame size");
	Check(prepared.destination.x == 0 && prepared.destination.y == 84
	          && prepared.destination.w == 640 && prepared.destination.h == 312,
	      "prepared indexed movie destination was not 640x312 at y84");
	Check(!prepared.approximate_border, "exact nonzero black palette entry was treated as approximate");
	Check(PixelAt(prepared.surface, 0, 0) == 7U
	          && PixelAt(prepared.surface, 0, 83) == 7U
	          && PixelAt(prepared.surface, 0, 84) == 42U
	          && PixelAt(prepared.surface, 320, 240) == 42U
	          && PixelAt(prepared.surface, 0, 396) == 7U,
	      "indexed movie pixels or letterbox border were not preserved");
	Check(prepared.surface->format->palette->colors[42].r
	          == source.value->format->palette->colors[42].r
	          && prepared.surface->format->palette->colors[42].g
	          == source.value->format->palette->colors[42].g
	          && prepared.surface->format->palette->colors[42].b
	          == source.value->format->palette->colors[42].b,
	      "indexed movie palette was not copied");

	const SDL_Color changed = {11, 22, 33, SDL_ALPHA_OPAQUE};
	Check(SDL_SetPaletteColors(source.value->format->palette, &changed, 42, 1) == 0,
	      "could not change the cinematic palette");
	prepared = adapter.Prepare(source.value);
	Check(prepared.error == PrepareError::None && !prepared.approximate_border,
	      "dynamic cinematic palette update failed");
	Check(prepared.surface->format->palette->colors[42].r == 11
	          && prepared.surface->format->palette->colors[42].g == 22
	          && prepared.surface->format->palette->colors[42].b == 33,
	      "dynamic cinematic palette was not published to the scratch surface");

	Surface no_black_source = MakeGeometrySurface(320, 156, 43U, 0U, false);
	IndexedFrameAdapter approximate_adapter;
	const auto approximate = approximate_adapter.Prepare(no_black_source.value);
	Check(approximate.error == PrepareError::None && approximate.surface != nullptr,
	      "movie without exact black palette entry was rejected");
	Check(approximate.approximate_border, "missing exact black palette entry was not diagnosed");
	Check(approximate_adapter.ConsumeApproximateBorderNotice(true)
	          && !approximate_adapter.ConsumeApproximateBorderNotice(true),
	      "approximate letterbox diagnostic was not one-time");
	Check(PixelAt(approximate.surface, 320, 240) == 43U,
	      "movie pixels were lost when letterbox black was approximate");

	IndexedFrameAdapter invalid_adapter;
	const auto invalid = invalid_adapter.Prepare(nullptr);
	Check(invalid.surface == nullptr && invalid.error == PrepareError::InvalidSurface,
	      "invalid cinematic surface was not rejected");
	Check(invalid_adapter.ConsumeErrorNotice() && !invalid_adapter.ConsumeErrorNotice(),
	      "invalid cinematic surface diagnostic was not one-time");
}

struct PublishedFrame {
	std::uint64_t frame_id = 0;
	std::uint64_t logic_tick = 0;
	std::uint8_t pixel0 = 0;
	std::uint8_t pixel_last = 0;
	std::array<std::uint8_t, 3> palette0 {};
};

std::vector<PublishedFrame> DrainReady(AbiView view, std::uint32_t epoch,
                                       std::uint32_t display_epoch)
{
	std::vector<PublishedFrame> result;
	Header &header = view.header();
	for (std::uint32_t slot = 0; slot < FRAME_SLOTS; ++slot) {
		const auto state = std::atomic_ref<std::uint32_t>(header.frames[slot].state)
		                       .load(std::memory_order_acquire);
		if (state != static_cast<std::uint32_t>(FrameState::Ready)
		    || !view.FpgaClaimReadyFrame(slot, epoch))
			continue;
		const auto frame = header.frames[slot];
		const auto memory = view.memory();
		PublishedFrame frame_result {
			.frame_id = frame.frame_id,
			.logic_tick = frame.logic_tick,
			.pixel0 = std::to_integer<std::uint8_t>(memory[frame.pixel_offset]),
			.pixel_last = std::to_integer<std::uint8_t>(
			    memory[frame.pixel_offset + frame.pixel_bytes - 1U]),
			.palette0 = {
				std::to_integer<std::uint8_t>(memory[frame.palette_offset + 0U]),
				std::to_integer<std::uint8_t>(memory[frame.palette_offset + 1U]),
				std::to_integer<std::uint8_t>(memory[frame.palette_offset + 2U]),
			},
		};
		Check(view.FpgaRetireDisplayedFrame(slot, epoch, display_epoch),
		      "FPGA could not retire cinematic test frame");
		result.push_back(frame_result);
	}
	return result;
}

std::optional<PublishedFrame> ConsumeOne(AbiView view, std::uint32_t epoch,
                                         std::uint32_t display_epoch)
{
	const auto frames = DrainReady(view, epoch, display_epoch);
	if (frames.empty()) return std::nullopt;
	return frames.front();
}

void RequireFrame(const std::optional<PublishedFrame> &frame,
                  std::uint8_t pixel, std::uint8_t palette_seed,
                  std::uint64_t logic_tick, const char *message)
{
	Check(frame.has_value(), message);
	Check(frame->pixel0 == pixel && frame->pixel_last == pixel,
	      "published frame pixels did not identify the requested source");
	Check(frame->palette0[0] == palette_seed
	          && frame->palette0[1] == palette_seed

                 && frame->palette0[2] == palette_seed,
	      "published frame palette did not identify the requested source");
	Check(frame->logic_tick == logic_tick, "published frame logic tick changed");
}

} // namespace

int main(int argc, char **argv)
{
	if (argc != 3) Fail("expected shared-file and lock-file paths");
	const std::filesystem::path shared_path = argv[1];
	const std::filesystem::path lock_path = argv[2];
	SharedFile shared(shared_path);

	SetEnvironment("SDL_VIDEODRIVER", "dummy");
	SetEnvironment("DIABLO_MISTER_TRANSPORT", "1");
	SetEnvironment("DIABLO_MISTER_SHARED_PATH", shared_path.string());
	SetEnvironment("DIABLO_MISTER_TRANSPORT_LOCK", lock_path.string());
	SetEnvironment("DIABLO_MISTER_SESSION_EPOCH", "324508639");
	SetEnvironment("DIABLO_MISTER_PROFILE", "1");
	SetEnvironment("DIABLO_MISTER_COMMAND_SCENE", "0");

	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVENTS) != 0) Fail(SDL_GetError());
	RunMovieFrameGeometryChecks();
	Surface title = MakeSurface(0x17U, 0x21U);
	Surface movie_a = MakeSurface(0xA6U, 0x42U);
	Surface movie_b = MakeSurface(0xD3U, 0x84U);

	auto &adapter = Adapter::Instance();
	adapter.Shutdown();
	Check(adapter.Initialize(), "production Adapter failed to initialize");
	Check(adapter.Active(), "production Adapter was not active");
	SetFpgaState(*shared.header, ComponentState::Ready);
	auto attached = AbiView::Attach({static_cast<std::byte *>(shared.mapping), SHARED_BYTES});
	Check(attached.has_value(), "test could not attach the shared ABI view");
	const std::uint32_t epoch = shared.header->session_epoch;

	// Title frame establishes the old source and its palette.
	Check(adapter.Present(title.value, 100U), "title frame was not published");
	RequireFrame(ConsumeOne(*attached, epoch, 1U), 0x17U, 0x21U, 100U,
	             "title frame was not observable");

	// Two changing cinematic frames must carry their own pixels and palette,
	// rather than the still-live PalSurface title.
	Check(adapter.Present(movie_a.value, 200U), "first cinematic frame was not published");
	RequireFrame(ConsumeOne(*attached, epoch, 2U), 0xA6U, 0x42U, 200U,
	             "first cinematic frame was replaced by the title");
	Check(adapter.Present(movie_b.value, 300U), "second cinematic frame was not published");
	RequireFrame(ConsumeOne(*attached, epoch, 3U), 0xD3U, 0x84U, 300U,
	             "second cinematic frame was replaced by stale content");

	// A full pipeline must report backpressure without publishing either movie
	// or the stale title. The generated movie hook is responsible for returning
	// from BlitFrame after this result instead of calling generic RenderPresent.
	for (unsigned index = 0; index < FRAME_SLOTS; ++index)
		Check(adapter.Present(title.value, 400U + index),
		      "could not fill the frame pipeline before backpressure");
	Check(!adapter.Present(movie_a.value, 500U),
	      "cinematic backpressure was not reported by the production Adapter");
	const auto retained = DrainReady(*attached, epoch, 4U);
	Check(retained.size() == FRAME_SLOTS,
	      "backpressure did not leave the existing title frames observable");
	for (const auto &frame : retained) {
		Check(frame.pixel0 == 0x17U && frame.pixel_last == 0x17U,
		      "backpressure published a movie or partial frame over the title");
		Check(frame.palette0[0] == 0x21U && frame.palette0[1] == 0x21U
		          && frame.palette0[2] == 0x21U,
		      "backpressure changed the title palette");
		Check(frame.logic_tick >= 400U && frame.logic_tick <= 402U,
		      "backpressure changed a retained title tick");
	}

	// The failed attempt above must not have fallen through to the stale title.
	// All retained slots were retired by DrainReady, so the next movie has room.
	Check(adapter.Present(movie_b.value, 600U), "movie did not publish after slot retirement");
	RequireFrame(ConsumeOne(*attached, epoch, 6U), 0xD3U, 0x84U, 600U,
	             "movie-after-backpressure was not published");

	// The title resumes after the movie source returns to the normal path.
	Check(adapter.Present(title.value, 700U), "title did not resume after cinematic frames");
	RequireFrame(ConsumeOne(*attached, epoch, 7U), 0x17U, 0x21U, 700U,
	             "return-to-title published stale cinematic content");

	adapter.Shutdown();
	SetEnvironment("DIABLO_MISTER_TRANSPORT", "0");
	Check(!adapter.Initialize(), "disabled transport unexpectedly initialized");
	SDL_Quit();
	std::puts("cinematic transport adapter checks passed");
	return EXIT_SUCCESS;
}
