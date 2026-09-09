// SPDX-License-Identifier: GPL-2.0-or-later
#define SDL_MAIN_HANDLED

#include <SDL.h>

#include "mister_transport_sdl.hpp"
#include "transport_abi.hpp"

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <string>
#include <thread>
#include <unistd.h>
#include <sys/mman.h>

namespace {

using diablo::mister::sdl::Adapter;
using diablo::mister::transport::ComponentState;
using diablo::mister::transport::FRAME_SLOTS;
using diablo::mister::transport::FrameState;
using diablo::mister::transport::Header;
using diablo::mister::transport::MAGIC;
using diablo::mister::transport::SHARED_BYTES;

[[noreturn]] void Fail(const char *message)
{
	std::fprintf(stderr, "transport lifecycle regression failure: %s\n", message);
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

std::string Decimal(std::uint32_t value)
{
	return std::to_string(value);
}

struct SharedFile {
	int fd = -1;
	void *mapping = MAP_FAILED;
	Header *header = nullptr;

	SharedFile(const std::filesystem::path &path)
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

bool IsFree(const Header &header)
{
	for (std::uint32_t slot = 0; slot < FRAME_SLOTS; ++slot) {
		if (std::atomic_ref<const std::uint32_t>(header.frames[slot].state).load(
		    std::memory_order_acquire)
		    != static_cast<std::uint32_t>(FrameState::Free))
			return false;
	}
	return true;
}

struct AudioMix {
	unsigned calls = 0;
	static void Mix(void *userdata, std::uint8_t *bytes, int count)
	{
		auto &self = *static_cast<AudioMix *>(userdata);
		++self.calls;
		std::memset(bytes, 0x21, static_cast<std::size_t>(count));
	}
};

void CheckAudioRefill(Adapter &adapter, Header &header)
{
	std::array<std::uint8_t, 4096> bytes {};
	AudioMix mix;
	header.pcm.consumer_sequence = header.pcm.producer_sequence;
	header.pcm.flags = 0;
	Check(adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size()) == 4,
	      "empty audio queue was not primed in bounded work");
	const auto primed = header.pcm.producer_sequence - header.pcm.consumer_sequence;
	Check(primed >= 8192 && primed <= 8920, "incorrect PCM startup lead");
	Check(adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size()) == 0,
	      "full DDR queue advanced the mixer");
	header.pcm.consumer_sequence = header.pcm.producer_sequence;
	header.pcm.flags = primed;
	Check(adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size()) == 0,
	      "local FPGA queue was ignored when deciding mixer demand");
	const auto calls_before_invalid = mix.calls;
	SetFpgaState(header, ComponentState::Fault);
	Check(adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size()) == 0,
	      "faulted transport advanced the mixer");
	SetFpgaState(header, ComponentState::Ready);
	const auto epoch = header.pcm.epoch;
	header.pcm.epoch ^= 1U;
	Check(adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size()) == 0,
	      "stale audio epoch advanced the mixer");
	header.pcm.epoch = epoch;
	Check(mix.calls == calls_before_invalid, "rejected audio request mixed samples");

	// Replay slow/fast dummy wakeups against an independent 48 kHz sink.
	// Include recurring 100 ms scheduler stalls. The legacy fixed-chunk path
	// must reproduce starvation; demand-based mixing must keep every sample.
	for (unsigned mode = 0; mode != 3; ++mode) {
		header.pcm.consumer_sequence = header.pcm.producer_sequence;
		header.pcm.flags = 0;
		(void)adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size());
		std::uint32_t queued = header.pcm.producer_sequence - header.pcm.consumer_sequence;
		header.pcm.consumer_sequence = header.pcm.producer_sequence;
		unsigned underruns = 0;
		unsigned multiple = 0;
		unsigned skipped = 0;
		std::uint32_t minimum = queued;
		const auto producer_start = header.pcm.producer_sequence;
		const auto mix_start = mix.calls;
		for (unsigned wakeup = 0; wakeup != 1000; ++wakeup) {
			const unsigned interval_us = (mode == 2 ? 45000 : 46710)
			    + ((wakeup % 137 == 136) ? 100000 : 0);
			const unsigned consumed = interval_us * 48U / 1000U;
			if (consumed > queued) { ++underruns; queued = 0; }
			else queued -= consumed;
			minimum = std::min(minimum, queued);
			header.pcm.flags = queued;
			unsigned chunks;
			if (mode == 0) {
				AudioMix::Mix(&mix, bytes.data(), bytes.size());
				Check(adapter.PublishPcmBytes(bytes.data(), bytes.size()), "legacy publish failed");
				chunks = 1;
			} else {
				chunks = adapter.ServicePcmAudio(AudioMix::Mix, &mix, bytes.data(), bytes.size());
			}
			Check(chunks <= 4, "audio refill work was unbounded");
			multiple += chunks > 1;
			skipped += chunks == 0;
			queued += header.pcm.producer_sequence - header.pcm.consumer_sequence;
			header.pcm.consumer_sequence = header.pcm.producer_sequence;
			Check(queued <= 10422, "audio lead grew without bound");
		}
		const auto published = header.pcm.producer_sequence - producer_start;
		const auto expected = static_cast<std::uint64_t>(mix.calls - mix_start) * 1024U * 48000U / 22050U;
		Check(published <= expected + 2 && published + 2 >= expected,
		      "mixed samples were dropped or repeated");
		if (mode == 0) Check(underruns > 0, "legacy pacing did not reproduce starvation");
		else {
			Check(underruns == 0 && minimum > 0, "demand-driven audio starved");
			Check(multiple > 0, "late callbacks did not catch up");
			if (mode == 2) Check(skipped > 0, "fast clock did not stop unnecessary mixing");
		}
		std::printf("PCM pacing mode=%u underruns=%u minimum=%u catchups=%u skipped=%u\n",
		            mode, underruns, minimum, multiple, skipped);
	}
	header.pcm.consumer_sequence = header.pcm.producer_sequence;
	header.pcm.flags = 0;
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
	SetEnvironment("DIABLO_MISTER_PROFILE", "0");
	SetEnvironment("DIABLO_MISTER_COMMAND_SCENE", "0");

	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVENTS) != 0) Fail(SDL_GetError());
	SDL_Surface *surface = SDL_CreateRGBSurfaceWithFormat(0, 640, 480, 8, SDL_PIXELFORMAT_INDEX8);
	if (surface == nullptr || surface->format == nullptr || surface->format->palette == nullptr)
		Fail("could not create indexed SDL surface");
	std::memset(surface->pixels, 0x2a, static_cast<std::size_t>(surface->pitch) * surface->h);
	std::array<SDL_Color, 256> palette {};
	for (std::size_t index = 0; index < palette.size(); ++index) {
		palette[index].r = static_cast<std::uint8_t>(index);
		palette[index].g = static_cast<std::uint8_t>(255U - index);
		palette[index].b = static_cast<std::uint8_t>(index ^ 0x5aU);
		palette[index].a = SDL_ALPHA_OPAQUE;
	}
	if (SDL_SetPaletteColors(surface->format->palette, palette.data(), 0, 256) != 0)
		Fail("could not initialize indexed SDL palette");

	auto &adapter = Adapter::Instance();
	adapter.Shutdown(); // prove idempotent shutdown from the initial inactive state.
	std::array<std::uint8_t, 4> audio_bytes {0, 0, 0, 0};
	std::uint32_t rebind_old_epoch = 0;
	std::uint32_t rebind_new_epoch = 0;
	std::uint64_t callback_calls = 0;
	std::uint64_t callback_accepted = 0;
	std::uint64_t callback_rejected = 0;
	constexpr unsigned kCycles = 64;

	for (unsigned cycle = 0; cycle < kCycles; ++cycle) {
		const std::uint32_t requested_epoch = 0x71000000U + cycle + 1U;
		SetEnvironment("DIABLO_MISTER_SESSION_EPOCH", Decimal(requested_epoch));
		Check(adapter.Initialize(), "production adapter failed to initialize");
		Check(adapter.Active(), "adapter was not active after initialize");
		Check(shared.header->session_epoch == requested_epoch,
		      "file-backed runtime did not publish the requested epoch");
		Check(adapter.Initialize(), "idempotent production initialize failed");
		Check(shared.header->session_epoch == requested_epoch,
		      "idempotent initialize changed the active epoch");

		SetFpgaState(*shared.header, ComponentState::Ready);
		if (cycle == 0) {
			rebind_old_epoch = shared.header->session_epoch;
			SetFpgaState(*shared.header, ComponentState::Fault);
			Check(!adapter.Present(nullptr, 100),
			      "fault recovery accepted an invalid surface");
			rebind_new_epoch = shared.header->session_epoch;
			Check(rebind_new_epoch != rebind_old_epoch,
			      "production Present did not rebind to a fresh epoch");
			Check(shared.header->arm_state == static_cast<std::uint32_t>(ComponentState::Ready)
			          && shared.header->magic == MAGIC && IsFree(*shared.header),
			      "epoch rebind did not reset the production transport state");
			SetFpgaState(*shared.header, ComponentState::Ready);
		}

		Check(adapter.Present(surface, cycle + 1U),
		      "production adapter failed to present a file-backed indexed frame");
		Check(adapter.PublishPcmBytes(audio_bytes.data(), audio_bytes.size()),
		      "production audio callback publication failed while active");

		if (cycle == 0) {
			CheckAudioRefill(adapter, *shared.header);
			std::atomic<bool> stop {false};
			std::atomic<std::uint64_t> calls {0};
			std::atomic<std::uint64_t> accepted {0};
			std::atomic<std::uint64_t> rejected {0};
			std::thread callback([&] {
				while (!stop.load(std::memory_order_acquire)) {
					calls.fetch_add(1, std::memory_order_relaxed);
					if (adapter.PublishPcmBytes(audio_bytes.data(), audio_bytes.size()))
						accepted.fetch_add(1, std::memory_order_relaxed);
					else
						rejected.fetch_add(1, std::memory_order_relaxed);
					std::this_thread::yield();
				}
			});
			const auto accepted_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
			while (accepted.load(std::memory_order_acquire) == 0
			       && std::chrono::steady_clock::now() < accepted_deadline)
				std::this_thread::yield();
			adapter.Shutdown();
			Check(!adapter.PublishPcmBytes(audio_bytes.data(), audio_bytes.size()),
			      "audio callback was admitted after production shutdown");
			const auto rejection_deadline = std::chrono::steady_clock::now()
				+ std::chrono::milliseconds(100);
			while (rejected.load(std::memory_order_acquire) == 0
			       && std::chrono::steady_clock::now() < rejection_deadline)
				std::this_thread::yield();
			stop.store(true, std::memory_order_release);
			callback.join();
			callback_calls = calls.load(std::memory_order_relaxed);
			callback_accepted = accepted.load(std::memory_order_relaxed);
			callback_rejected = rejected.load(std::memory_order_relaxed);
			Check(callback_rejected > 0,
			      "concurrent audio callback did not observe production shutdown");
		} else {
			adapter.Shutdown();
		}
		Check(!adapter.Active(), "adapter remained active after shutdown");
		adapter.Shutdown();
		Check(!adapter.Active(), "idempotent production shutdown reactivated runtime");
	}

	Check(callback_calls > 0 && callback_accepted > 0 && callback_rejected > 0,
	      "callback admission did not observe both active and shutdown states");
	SDL_FreeSurface(surface);
	SDL_Quit();
	std::printf("transport lifecycle regression PASS cycles=%u rebind_old_epoch=%u "
	            "rebind_new_epoch=%u callback_calls=%llu callback_accepted=%llu "
	            "callback_rejected=%llu\n",
	            kCycles, rebind_old_epoch, rebind_new_epoch,
	            static_cast<unsigned long long>(callback_calls),
	            static_cast<unsigned long long>(callback_accepted),
	            static_cast<unsigned long long>(callback_rejected));
	return EXIT_SUCCESS;
}
