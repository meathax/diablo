// SPDX-License-Identifier: GPL-2.0-or-later
// Read-only target diagnostic for the admitted MiSTer transport aperture.
// DIABLO_MISTER_SHARED_PATH selects a file-backed ABI image for host tests.
#include "transport_abi.hpp"

#include <cinttypes>
#include <cstdlib>
#include <cstdio>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

using namespace diablo::mister::transport;

namespace {

constexpr off_t kPhysicalBase = 0x3FE00000;

} // namespace

int main()
{
	const char *file_backed_path = std::getenv("DIABLO_MISTER_SHARED_PATH");
	const bool file_backed = file_backed_path != nullptr && *file_backed_path != '\0';
	const int fd = file_backed
	             ? ::open(file_backed_path, O_RDONLY)
	             : ::open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		std::perror(file_backed ? "open shared fixture" : "open /dev/mem");
		return 1;
	}
	if (file_backed) {
		struct stat file_status {};
		if (::fstat(fd, &file_status) != 0) {
			std::perror("stat shared fixture");
			::close(fd);
			return 1;
		}
		if (file_status.st_size < static_cast<off_t>(SHARED_BYTES)) {
			std::fprintf(stderr, "shared fixture is shorter than %u bytes\n", SHARED_BYTES);
			::close(fd);
			return 1;
		}
	}
	void *mapping = ::mmap(nullptr, SHARED_BYTES, PROT_READ,
	                       file_backed ? MAP_PRIVATE : MAP_SHARED, fd,
	                       file_backed ? 0 : kPhysicalBase);
	if (mapping == MAP_FAILED) {
		std::perror("mmap shared DDR");
		::close(fd);
		return 1;
	}
	auto attached = AbiView::Attach({static_cast<std::byte *>(mapping), SHARED_BYTES});
	if (!attached.has_value()) {
		std::printf("attach_error=%u\n", static_cast<unsigned>(attached.error()));
		::munmap(mapping, SHARED_BYTES);
		::close(fd);
		return 1;
	}
	const Header &header = attached->header();
	const auto validation = attached->Validate(header.session_epoch);
	if (!validation.has_value()) {
		std::printf("validate_error=%u\n", static_cast<unsigned>(validation.error()));
		::munmap(mapping, SHARED_BYTES);
		::close(fd);
		return 1;
	}
	const auto pcm_health = attached->ReadPcmHealth(header.session_epoch);
	std::printf("magic=%c%c%c%c%c%c%c%c abi=%u.%u control=%" PRIu32
	            " shared=%" PRIu32 " endian=0x%08" PRIx32
	            " capabilities=0x%08" PRIx32 "\n",
	            header.magic[0], header.magic[1], header.magic[2], header.magic[3],
	            header.magic[4], header.magic[5], header.magic[6], header.magic[7],
	            header.abi_major, header.abi_minor, header.control_bytes,
	            header.shared_bytes, header.little_endian_tag, header.capabilities);
	if (pcm_health.has_value()) {
		std::printf("epoch=0x%08" PRIx32 " arm=%" PRIu32 " fpga=%" PRIu32
		            " fault=%" PRIu32 " detail=0x%08" PRIx32 " display_epoch=0x%08" PRIx32
		            " last_frame=%" PRIu64 " input_prod=%" PRIu32 " input_cons=%" PRIu32
		            " input_dropped=%" PRIu64 " pcm_prod=%" PRIu32 " pcm_cons=%" PRIu32
		            " pcm_queued_frames=%" PRIu32 " pcm_local_queue_frames=%" PRIu32
		            " pcm_underruns=%" PRIu32 " pcm_resyncs=%" PRIu32
		            " cmd_prod=%" PRIu32 " cmd_cons=%" PRIu32
		            " payload_prod=%" PRIu32 " payload_cons=%" PRIu32
		            " completed_fence=0x%016" PRIx64 "\n",
		            header.session_epoch, header.arm_state, header.fpga_state,
		            header.fault_code, header.fault_detail, header.display_epoch,
		            header.last_presented_frame_id,
		            header.input.producer_sequence, header.input.consumer_sequence,
		            header.input.dropped, pcm_health->producer_sequence,
		            pcm_health->consumer_sequence, pcm_health->queued_frames,
		            pcm_health->local_queue_frames, pcm_health->underrun_count,
		            pcm_health->resync_count,
				header.command_records.producer_sequence,
				header.command_records.consumer_sequence,
				header.command_payload.producer_sequence,
				header.command_payload.consumer_sequence,
				header.last_completed_fence);
	} else {
		std::printf("epoch=0x%08" PRIx32 " arm=%" PRIu32 " fpga=%" PRIu32
		            " fault=%" PRIu32 " detail=0x%08" PRIx32 " display_epoch=0x%08" PRIx32
		            " last_frame=%" PRIu64 " input_prod=%" PRIu32 " input_cons=%" PRIu32
		            " input_dropped=%" PRIu64 " pcm_prod=%" PRIu32 " pcm_cons=%" PRIu32
		            " pcm_health_error=%u"
		            " cmd_prod=%" PRIu32 " cmd_cons=%" PRIu32
		            " payload_prod=%" PRIu32 " payload_cons=%" PRIu32
		            " completed_fence=0x%016" PRIx64 "\n",
		            header.session_epoch, header.arm_state, header.fpga_state,
		            header.fault_code, header.fault_detail, header.display_epoch,
		            header.last_presented_frame_id,
		            header.input.producer_sequence, header.input.consumer_sequence,
		            header.input.dropped, header.pcm.producer_sequence,
		            header.pcm.consumer_sequence,
		            static_cast<unsigned>(pcm_health.error()),
				header.command_records.producer_sequence,
				header.command_records.consumer_sequence,
				header.command_payload.producer_sequence,
				header.command_payload.consumer_sequence,
				header.last_completed_fence);
	}
	for (std::uint32_t slot = 0; slot < FRAME_SLOTS; ++slot) {
		const auto &frame = header.frames[slot];
		std::printf("frame[%u] state=%" PRIu32 " gen=0x%08" PRIx32
		            " id=%" PRIu64 " tick=%" PRIu64 " display=0x%08" PRIx32
		            " crc=0x%08" PRIx32 " pixel=0x%08" PRIx32 "/%" PRIu32
		            " palette=0x%08" PRIx32 "/%" PRIu32
		            " producer=0x%08" PRIx32 "\n",
		            slot, frame.state, frame.generation, frame.frame_id,
		            frame.logic_tick, frame.display_epoch, frame.crc32,
		            frame.pixel_offset, frame.pixel_bytes, frame.palette_offset,
		            frame.palette_bytes, frame.producer_epoch);
	}
	::munmap(mapping, SHARED_BYTES);
	::close(fd);
	return 0;
}
