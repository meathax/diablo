#include "transport_abi.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#include <unistd.h>

namespace {

using namespace diablo::mister::transport;

[[noreturn]] void Fail(const std::string &message)
{
	std::cerr << "transport state dump test failure: " << message << '\n';
	std::exit(1);
}

void Require(bool condition, const std::string &message)
{
	if (!condition) Fail(message);
}

std::string ShellQuote(const std::filesystem::path &path)
{
	std::string quoted = "'" + path.string();
	std::size_t offset = 1;
	while ((offset = quoted.find('\'', offset)) != std::string::npos) {
		quoted.replace(offset, 1, "'\\''");
		offset += 4;
	}
	return quoted + "'";
}

std::string ReadText(const std::filesystem::path &path)
{
	std::ifstream input(path);
	return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

int RunDump(const std::filesystem::path &utility,
			const std::filesystem::path &fixture,
			const std::filesystem::path &output)
{
	::setenv("DIABLO_MISTER_SHARED_PATH", fixture.c_str(), 1);
	const std::string command = ShellQuote(std::filesystem::absolute(utility))
	                          + " > " + ShellQuote(output) + " 2>&1";
	const int status = std::system(command.c_str());
	::unsetenv("DIABLO_MISTER_SHARED_PATH");
	return status;
}

} // namespace

int main(int argc, char **argv)
{
	if (argc != 2) Fail("expected path to transport_state_dump executable");

	constexpr std::uint32_t epoch = 0xA5010204U;
	std::vector<std::byte> memory(SHARED_BYTES);
	auto attached = AbiView::Attach(memory);
	Require(attached.has_value(), "fixture mapping did not attach");
	Require(attached->InitializeArm(epoch), "fixture ABI initialization failed");
	Header &header = attached->header();
	header.fpga_state = static_cast<std::uint32_t>(ComponentState::Ready);
	header.display_epoch = 0x00001234U;
	header.last_presented_frame_id = 99;
	header.pcm.producer_sequence = 128;
	header.pcm.consumer_sequence = 96;
	header.pcm.flags = 2048;
	header.pcm.dropped = (std::uint64_t {7} << 32U) | 3U;
	header.pcm_underflow_snapshot = PcmUnderflowSnapshot {
		.event_cycle = 1234U,
		.session_epoch = epoch,
		.producer_sequence = 128U,
		.fetch_sequence = 128U,
		.published_consumer = 128U,
		.underrun_count = 4U,
		.queue_depth = 0U,
		.player_state = 0x5d3U,
		.arbiter_diagnostic = 0x0123456789abcdefULL,
		.resync_count = 0U,
		.commit_sequence = 1U,
	};

	const auto prefix = std::filesystem::temp_directory_path()
	                  / ("diablo-transport-state-dump-" + std::to_string(::getpid()));
	const auto fixture = prefix.string() + "-fixture.bin";
	const auto output = prefix.string() + "-output.txt";
	const auto missing_fixture = prefix.string() + "-missing.bin";
	const auto short_fixture = prefix.string() + "-short.bin";
	const auto malformed_fixture = prefix.string() + "-malformed.bin";
	{
		std::ofstream stream(fixture, std::ios::binary | std::ios::trunc);
		Require(stream.good(), "could not create file-backed fixture");
		stream.write(reinterpret_cast<const char *>(memory.data()),
		            static_cast<std::streamsize>(memory.size()));
		Require(stream.good(), "could not write file-backed fixture");
	}

	const std::filesystem::path utility = argv[1];
	const int status = RunDump(utility, fixture, output);
	Require(status == 0, "diagnostic executable failed on file-backed fixture");

	const std::string dump = ReadText(output);
	Require(dump.find("epoch=0xa5010204 arm=1 fpga=1 fault=0") != std::string::npos,
	        "lifecycle identity was not printed");
	Require(dump.find("pcm_prod=128 pcm_cons=96 pcm_queued_frames=32") != std::string::npos,
	        "shared PCM queue occupancy was not printed");
	Require(dump.find("pcm_local_queue_frames=2048 pcm_underruns=3 pcm_resyncs=7") != std::string::npos,
	        "FPGA-local PCM health was not printed");
	Require(dump.find("pcm_underflow_event_cycle=1234 epoch=0xa5010204 producer=128 fetch=128 consumer=128") != std::string::npos,
	        "committed PCM underflow snapshot was not printed");
	Require(dump.find("arbiter=0x0123456789abcdef resyncs=0 commit=1") != std::string::npos,
	        "PCM underflow arbitration diagnostic was not printed");

	// The same ARM utility must remain read-only and useful with a pre-snapshot
	// FPGA image, which leaves the session-cleared optional tail uncommitted.
	header.pcm_underflow_snapshot = {};
	{
		std::ofstream stream(fixture, std::ios::binary | std::ios::trunc);
		Require(stream.good(), "could not rewrite old-FPGA fixture");
		stream.write(reinterpret_cast<const char *>(memory.data()),
		            static_cast<std::streamsize>(memory.size()));
		Require(stream.good(), "could not write old-FPGA fixture");
	}
	Require(RunDump(utility, fixture, output) == 0,
	        "diagnostic executable failed on uncommitted PCM snapshot");
	Require(ReadText(output).find("pcm_underflow=unavailable") != std::string::npos,
	        "uncommitted optional PCM snapshot was not reported as unavailable");

	{
		std::ofstream stream(short_fixture, std::ios::binary | std::ios::trunc);
		Require(stream.good(), "could not create short fixture");
		stream.put('\0');
	}
	Require(RunDump(utility, short_fixture, output) != 0,
	        "short fixture was accepted");
	const std::string short_output = ReadText(output);
	Require(short_output.find("shared fixture is shorter than") != std::string::npos,
	        "short fixture rejection was not reported");

	{
		std::ofstream stream(malformed_fixture, std::ios::binary | std::ios::trunc);
		Require(stream.good(), "could not create malformed fixture");
		stream.seekp(static_cast<std::streamoff>(SHARED_BYTES) - 1);
		stream.put('\0');
	}
	Require(RunDump(utility, malformed_fixture, output) != 0,
	        "malformed fixture was accepted");
	const std::string malformed_output = ReadText(output);
	Require(malformed_output.find("validate_error=") != std::string::npos,
	        "malformed fixture rejection was not reported");

	Require(RunDump(utility, missing_fixture, output) != 0,
	        "missing fixture was accepted");
	const std::string missing_output = ReadText(output);
	Require(missing_output.find("open shared fixture") != std::string::npos,
	        "missing fixture rejection was not reported");

	for (const auto &path : {fixture, output, short_fixture, malformed_fixture})
		std::filesystem::remove(path);
	std::cout << "transport state dump file-backed output test passed\n";
}
