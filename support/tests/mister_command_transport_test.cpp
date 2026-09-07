#include "mister_command_transport.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <span>
#include <vector>

using diablo::mister::command::Publisher;
using diablo::mister::command::Record;
using diablo::mister::transport::AbiView;
using diablo::mister::transport::COMMAND_PAYLOAD_OFFSET;
using diablo::mister::transport::COMMAND_RECORDS_OFFSET;
using diablo::mister::transport::COMMAND_RECORDS_RECORD_BYTES;
using diablo::mister::transport::SHARED_BYTES;

namespace {

void Require(bool condition, const char *message)
{
	if (!condition) {
		std::cerr << message << '\n';
		std::exit(1);
	}
}

} // namespace

int main()
{
	std::vector<std::byte> memory(SHARED_BYTES);
	auto attached = AbiView::Attach(memory);
	Require(attached.has_value(), "command fixture did not attach");
	Require(attached->InitializeArm(0x71020304U), "command fixture did not initialize");
	Publisher publisher(*attached, 0x71020304U);

	std::array<Record, 3> records {{
		{ 1, 0x55, 1, 2, 3, 4, 0, 0 },
		{ 2, 0, 4, 5, 6, 7, 0, 0 },
		{ 0xffff, 0, 0, 0, 0, 0, 0, 9 },
	}};
	std::array<std::byte, 11> payload {};
	for (std::size_t index = 0; index < payload.size(); ++index)
		payload[index] = static_cast<std::byte>(index + 1);
	auto published = publisher.Publish(records, payload);
	Require(published.has_value() && *published == 3, "initial command batch did not publish");
	Require(attached->header().command_records.producer_sequence == 3
	            && attached->header().command_payload.producer_sequence == payload.size(),
	        "command producer cursors were not published");
	const auto command_memory = attached->memory().subspan(COMMAND_RECORDS_OFFSET,
	                                                        COMMAND_RECORDS_RECORD_BYTES * 3U);
	Require(std::memcmp(command_memory.data(), records.data(), sizeof(records)) == 0,
	        "command record bytes were not copied");
	const auto payload_memory = attached->memory().subspan(COMMAND_PAYLOAD_OFFSET, payload.size());
	Require(std::memcmp(payload_memory.data(), payload.data(), payload.size()) == 0,
	        "command payload bytes were not copied");

	attached->header().command_records.producer_sequence = 2046;
	attached->header().command_records.consumer_sequence = 2046;
	std::array<Record, 4> wrapped {};
	Require(publisher.Publish(wrapped, std::span<const std::byte> {}).has_value(),
	        "wrapped command records failed");
	Require(attached->header().command_records.producer_sequence == 2050
	            && std::memcmp(attached->memory().data() + COMMAND_RECORDS_OFFSET,
	                           wrapped.data() + 2, sizeof(Record) * 2U) == 0,
	        "wrapped command records were not written at slot zero");

	attached->header().command_payload.producer_sequence = 196603;
	attached->header().command_payload.consumer_sequence = 196603;
	std::array<std::byte, 9> wrapped_payload {};
	for (std::size_t index = 0; index < wrapped_payload.size(); ++index)
		wrapped_payload[index] = static_cast<std::byte>(0xa0U + index);
	Require(publisher.Publish(std::span<const Record> {}, wrapped_payload).has_value(),
	        "wrapped command payload failed");
	Require(attached->header().command_payload.producer_sequence == 196612
	            && attached->memory()[COMMAND_PAYLOAD_OFFSET] == wrapped_payload[5],
	        "wrapped command payload was not written at slot zero");

	attached->header().command_records.producer_sequence = 2048;
	attached->header().command_records.consumer_sequence = 0;
	Require(!publisher.Publish(records, {}).has_value(), "full command ring accepted a batch");
	std::array<std::byte, 1> bad_memory {};
	auto bad_attach = AbiView::Attach(bad_memory);
	Require(!bad_attach.has_value(), "short command attachment was accepted");
	std::cout << "command transport publication checks passed\n";
}
