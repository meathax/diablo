#include "transport_abi.hpp"
#include "transport_input.hpp"
#include "mister_transport.hpp"

#include <array>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <span>
#include <vector>

namespace {

using diablo::mister::transport::AbiView;
using diablo::mister::transport::AttachError;
using diablo::mister::transport::ComponentState;
using diablo::mister::transport::FRAME_SLOTS;
using diablo::mister::transport::FRAME_CHECKSUM_ABSENT;
using diablo::mister::transport::FRAME_CHECKSUM_KIND_MASK;
using diablo::mister::transport::FRAME_CHECKSUM_SAMPLED_CRC32;
using diablo::mister::transport::FrameState;
using diablo::mister::transport::Header;
using diablo::mister::transport::InputEvent;
using diablo::mister::transport::InputSnapshot;
using diablo::mister::transport::InputConsumer;
using diablo::mister::transport::PublishError;
using diablo::mister::transport::TransportSession;
using diablo::mister::transport::INPUT_CAPACITY;
using diablo::mister::transport::INPUT_EVENT_KEYBOARD;
using diablo::mister::transport::INPUT_EVENT_MOUSE;
using diablo::mister::transport::INPUT_RECORD_BYTES;
using diablo::mister::transport::INPUT_REGION_OFFSET;
using diablo::mister::transport::SHARED_BYTES;
using diablo::mister::transport::FRAME_HEIGHT;
using diablo::mister::transport::FRAME_PIXEL_BYTES;
using diablo::mister::transport::FRAME_WIDTH;
using diablo::mister::transport::PALETTE_BYTES;

[[noreturn]] void Fail(const char *message)
{
	std::cerr << "transport ABI test failure: " << message << '\n';
	std::exit(1);
}

void Require(bool condition, const char *message)
{
	if (!condition)
		Fail(message);
}

void WriteHex(const std::span<const std::byte> bytes, const char *path)
{
	std::ofstream output(path);
	if (!output)
		Fail("cannot open fixture output");
	output << std::hex << std::setfill('0');
	for (const std::byte byte : bytes)
		output << std::setw(2) << static_cast<unsigned>(std::to_integer<unsigned char>(byte)) << '\n';
}

} // namespace

int main(int argc, char **argv)
{
	if (argc != 2)
		Fail("expected a hexadecimal fixture output path");

	std::vector<std::byte> tooSmall(SHARED_BYTES - 1);
	Require(!AbiView::Attach(tooSmall).has_value(), "undersized mapping was accepted");

	std::vector<std::byte> memory(SHARED_BYTES);
	auto attached = AbiView::Attach(memory);
	Require(attached.has_value(), "aligned two-megabyte mapping was rejected");
	AbiView view = *attached;
	Require(!view.InitializeArm(0), "zero session epoch was accepted");
	Require(view.InitializeArm(0xA5010204U), "initialization failed");
	Require(view.Validate(0xA5010204U).has_value(), "fresh layout did not validate");
	Require(!view.Validate(0xA5010205U).has_value(), "stale session epoch was accepted");

	auto frame = view.ArmBeginFrame(1, 0xA5010204U);
	Require(frame.has_value(), "free frame was not acquired by ARM");
	Require((*frame)->state == static_cast<std::uint32_t>(FrameState::ArmWriting), "ARM frame state was not published");
	Require(!view.ArmBeginFrame(1, 0xA5010204U).has_value(), "in-flight frame was reacquired");
	Require(view.ArmPublishFrame(1, 0xA5010204U, 0x0102030405060708ULL, 0x1122334455667788ULL,
	    0x1020304050607080ULL, 0x21436587U, FRAME_CHECKSUM_SAMPLED_CRC32), "ARM could not publish frame");
	Require(view.FpgaClaimReadyFrame(1, 0xA5010204U), "FPGA could not claim ready frame");
	Require(!view.ArmBeginFrame(1, 0xA5010204U).has_value(), "displayed frame was exposed to ARM");
	Require(view.FpgaRetireDisplayedFrame(1, 0xA5010204U, 17), "FPGA could not retire displayed frame");
	Require(view.ArmBeginFrame(1, 0xA5010204U).has_value(), "retired frame was not returned to ARM");

	view.header().frames[0].pixel_offset += 4;
	Require(!view.Validate(0xA5010204U).has_value(), "out-of-layout frame descriptor was accepted");
	Require(view.InitializeArm(0xA5010204U), "reinitialization failed");
	view.SignalFault(0x55AA11EEU, 0x01020408U);
	Require(view.header().fault_code == 0x55AA11EEU, "fault code was not retained");
	Require(view.header().arm_state == static_cast<std::uint32_t>(ComponentState::Fault), "fault state was not published");

	Require(view.InitializeArm(0xA5010204U), "fixture initialization failed");
	Header &header = view.header();
	header.pcm.producer_sequence = 128;
	header.pcm.consumer_sequence = 96;
	header.pcm.flags = 2048;
	header.pcm.dropped = (std::uint64_t { 7 } << 32U) | 3U;
	auto pcm_health = view.ReadPcmHealth(0xA5010204U);
	Require(pcm_health.has_value() && pcm_health->queued_frames == 32
	            && pcm_health->local_queue_frames == 2048
	            && pcm_health->underrun_count == 3 && pcm_health->resync_count == 7,
	        "PCM health snapshot was not observable");
	header.pcm.consumer_sequence = header.pcm.producer_sequence;
	header.pcm.dropped = 0;
	std::array<InputEvent, 2> input_events{};
	input_events[0] = InputEvent{17, 101, INPUT_EVENT_KEYBOARD, 0x1c, 1, 0, 0x44};
	input_events[1] = InputEvent{18, 102, INPUT_EVENT_MOUSE, 0x284, -2, 3, 0x55};
	std::memcpy(view.memory().data() + INPUT_REGION_OFFSET, &input_events[0], sizeof(InputEvent));
	std::memcpy(view.memory().data() + INPUT_REGION_OFFSET + INPUT_RECORD_BYTES,
	            &input_events[1], sizeof(InputEvent));
	header.input.producer_sequence = 2;
	header.input.consumer_sequence = 0;
	std::array<InputEvent, 2> consumed{};
	auto consumed_count = view.ArmConsumeInput(consumed, 0xA5010204U);
	Require(consumed_count.has_value() && *consumed_count == 2, "ARM did not consume input events");
	Require(consumed[0].type == INPUT_EVENT_KEYBOARD && consumed[1].value0 == -2,
	        "input event payload was not preserved");
	Require(header.input.consumer_sequence == 2, "input consumer cursor was not published");
	InputConsumer input_consumer(view, 0xA5010204U);
	header.input.consumer_sequence = 0;
	header.input.dropped = 0;
	std::array<InputEvent, 2> reducer_events{};
	auto reducer_count = input_consumer.Poll(reducer_events);
	Require(reducer_count.has_value() && *reducer_count == 2, "input consumer did not drain events");
	Require((input_consumer.state().keyboard[0] & (std::uint64_t { 1 } << 28)) != 0
	            && input_consumer.state().snapshot.mouse_dx == -2,
	        "input consumer did not reduce key and mouse state");
	header.input.dropped = 7;
	auto dropped = view.ArmInputDropped(0xA5010204U);
	Require(dropped.has_value() && *dropped == 7, "input dropped counter was not observable");
	auto recovery_result = input_consumer.Poll(reducer_events);
	Require(!recovery_result.has_value() && recovery_result.error() == AttachError::InputOverflow
	            && header.input_snapshot_sequence == 2 && header.input.consumer_sequence == 2,
	        "input consumer did not recover after a dropped edge");
	header.input.producer_sequence = INPUT_CAPACITY + 3;
	header.input.consumer_sequence = 0;
	auto overflow = view.ArmConsumeInput(consumed, 0xA5010204U);
	Require(!overflow.has_value() && overflow.error() == AttachError::InputOverflow,
	        "input overflow was not reported");
	InputSnapshot recovered{};
	recovered.buttons = 0x1234;
	recovered.mouse_dx = -9;
	Require(view.ArmRecoverInput(0xA5010204U, recovered), "input snapshot recovery failed");
	Require(header.input_snapshot_sequence == INPUT_CAPACITY + 3
	            && header.input.consumer_sequence == INPUT_CAPACITY + 3
	            && header.input_snapshot.mouse_dx == -9,
	        "input snapshot recovery did not resynchronize the cursor");

	std::vector<std::byte> session_memory(SHARED_BYTES);
	auto session_result = TransportSession::Attach(session_memory, 0xB6020305U);
	Require(session_result.has_value(), "transport session did not attach");
	TransportSession session = *session_result;
	std::vector<std::uint8_t> pixels(static_cast<std::size_t>(FRAME_WIDTH + 8U) * FRAME_HEIGHT);
	for (std::size_t row = 0; row < FRAME_HEIGHT; ++row)
		for (std::size_t column = 0; column < FRAME_WIDTH + 8U; ++column)
			pixels[row * (FRAME_WIDTH + 8U) + column] = static_cast<std::uint8_t>((row + column) & 0xffU);
	std::array<std::uint8_t, PALETTE_BYTES> palette {};
	for (std::size_t index = 0; index < palette.size(); ++index)
		palette[index] = static_cast<std::uint8_t>((index * 3U) & 0xffU);
	Require(session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 11).has_value(),
	        "first indexed frame was not published");
	Require(session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 12).has_value(),
	        "second indexed frame was not published");
	Require(session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 13).has_value(),
	        "third indexed frame was not published");
	auto blocked = session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 14);
	Require(!blocked.has_value() && blocked.error() == PublishError::Backpressure,
	        "full frame pipeline did not apply backpressure");
	Require(session.view().header().frames[0].state == static_cast<std::uint32_t>(FrameState::Ready),
	        "published frame was not left ready for FPGA ownership");
	Require(session.view().FpgaClaimReadyFrame(0, 0xB6020305U),
	        "FPGA could not claim the session frame");
	Require(session.view().FpgaRetireDisplayedFrame(0, 0xB6020305U, 1),
	        "FPGA could not retire the session frame");
	auto recycled = session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 14);
	Require(recycled.has_value() && *recycled == 4,
	        "freed frame slot was not recycled with a monotonic frame id");
	const auto &published = session.view().header().frames[0];
	Require(published.frame_id == 4 && published.logic_tick == 14
	            && published.crc32 != 0
	            && published.flags == FRAME_CHECKSUM_SAMPLED_CRC32,
	        "session frame metadata was not published");
	const auto frame_bytes = session.view().memory().subspan(published.pixel_offset, FRAME_PIXEL_BYTES);
	Require(std::to_integer<std::uint8_t>(frame_bytes[0]) == pixels[0]
	            && std::to_integer<std::uint8_t>(frame_bytes[FRAME_WIDTH]) == pixels[FRAME_WIDTH + 8U],
	        "session frame copy did not strip source pitch correctly");
	Require(!session.PublishIndexedFrame(pixels, FRAME_WIDTH - 1U, palette, 15).has_value(),
	        "short indexed rows were accepted");
	Require(!session.PublishIndexedFrame(pixels, std::numeric_limits<std::size_t>::max(), palette, 15).has_value(),
	        "overflowing indexed pitch was accepted");
	std::array<std::uint8_t, PALETTE_BYTES - 1U> short_palette {};
	Require(!session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, short_palette, 15).has_value(),
	        "short palette was accepted");
	// A command writer bypasses TransportSession and changes slot zero directly.
	// Its cached palette/shadow must be invalidated before the next full-copy
	// fallback, including the A -> B -> A palette sequence from the audit.
	Require(session.view().FpgaClaimReadyFrame(0, 0xB6020305U),
	        "FPGA could not claim cached palette fixture frame");
	Require(session.view().FpgaRetireDisplayedFrame(0, 0xB6020305U, 2),
	        "FPGA could not retire cached palette fixture frame");
	Require(session.view().ArmBeginFrameFast(0, 0xB6020305U).has_value(),
	        "command palette fixture could not claim a free slot");
	Require(session.InvalidateSlotContentCache(0), "command palette cache invalidation failed");
	const auto command_palette_offset = session.view().header().frames[0].palette_offset;
	std::memset(session.view().memory().data() + command_palette_offset, 0xA5, PALETTE_BYTES);
	Require(session.view().ArmPublishFrameFast(0, 0xB6020305U, 42, 42, 42, 0, FRAME_CHECKSUM_ABSENT),
	        "command palette fixture could not publish its direct write");
	Require(session.view().FpgaClaimReadyFrame(0, 0xB6020305U),
	        "FPGA could not claim direct palette fixture frame");
	Require(session.view().FpgaRetireDisplayedFrame(0, 0xB6020305U, 3),
	        "FPGA could not retire direct palette fixture frame");
	auto cache_recovered = session.PublishIndexedFrame(pixels, FRAME_WIDTH + 8U, palette, 15);
	Require(cache_recovered.has_value(), "cache-invalidated full-copy fallback did not publish");
	Require(std::memcmp(session.view().memory().data() + command_palette_offset,
	                    palette.data(), PALETTE_BYTES) == 0,
	        "full-copy fallback reused a stale command palette cache");
	Require(!session.InvalidateSlotContentCache(FRAME_SLOTS),
	        "out-of-range slot cache invalidation was accepted");
	Require(session.view().InitializeArm(0xB6020305U), "session abort fixture reset failed");
	Require(session.view().ArmBeginFrameFast(0, 0xB6020305U).has_value(),
	        "speculative command frame claim failed");
	Require(session.view().ArmAbortFrameFast(0, 0xB6020305U),
	        "speculative command frame abort failed");
	Require(session.view().header().frames[0].state == static_cast<std::uint32_t>(FrameState::Free),
	        "aborted command frame was not returned to the free pool");
	Require(session.view().InitializeArm(0xB6020305U), "command-timeout fixture reset failed");
	Require(session.view().ArmBeginFrameFast(0, 0xB6020305U).has_value(),
	        "command-timeout fixture could not claim a slot");
	Require(session.view().ArmFaultFrameFast(0, 0xB6020305U),
	        "timed-out command slot was not marked faulted");
	Require(session.view().header().frames[0].state == static_cast<std::uint32_t>(FrameState::Fault),
	        "timed-out command slot returned to a reusable state");
	Require(!session.view().ArmAbortFrameFast(0, 0xB6020305U)
	            && !session.view().ArmBeginFrameFast(0, 0xB6020305U).has_value(),
	        "faulted command slot could be recycled before an epoch reset");
	Require(view.InitializeArm(0xA5010204U), "checksum validation fixture reset failed");
	header.frames[0].flags = FRAME_CHECKSUM_KIND_MASK;
	Require(!view.Validate(0xA5010204U).has_value(),
	        "unknown checksum kind was accepted by ABI validation");

	Require(view.InitializeArm(0xA5010204U), "fixture reinitialization failed");
	header.input.producer_sequence = 0x01020408U;
	header.input.consumer_sequence = 0x10204080U;
	header.frames[2].state = static_cast<std::uint32_t>(FrameState::Fault);
	header.frames[2].frame_id = 0x0102030405060708ULL;
	header.frames[2].logic_tick = 0x1122334455667788ULL;
	header.frames[2].crc32 = 0x21436587U;
	header.frames[2].flags = FRAME_CHECKSUM_SAMPLED_CRC32;
	header.frames[2].fence = 0x1020304050607080ULL;
	header.input_snapshot.buttons = 0x8040201008040201ULL;
	header.input_snapshot.mouse_x = -12345;
	header.input_snapshot.mouse_y = 23456;
	header.input_snapshot.mouse_dx = -77;
	header.input_snapshot.mouse_dy = 88;
	header.input_snapshot.modifiers = 0x0F0E0D0CU;
	header.input_snapshot.focus_generation = 0x01010101U;
	WriteHex(view.memory().first(sizeof(Header)), argv[1]);
	std::cout << "transport ABI host checks passed\n";
}
