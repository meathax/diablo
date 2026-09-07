#pragma once

#include "mister_command_renderer.hpp"
#include "transport_abi.hpp"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <expected>
#include <span>

namespace diablo::mister::command {

enum class PublishError : std::uint32_t {
	InvalidEpoch,
	RecordBackpressure,
	PayloadBackpressure,
};

// ARM-side command-ring publisher. It only publishes bounded records and their
// payload bytes; a future FPGA consumer must validate the same epoch and fences
// before executing anything against a render target.
class Publisher {
public:
	Publisher(transport::AbiView view, std::uint32_t epoch)
		: view_(view)
		, epoch_(epoch)
	{
	}

	[[nodiscard]] std::expected<std::uint32_t, PublishError> Publish(
	    std::span<const Record> records, std::span<const std::byte> payload)
	{
		if (epoch_ == 0 || view_.header().session_epoch != epoch_)
			return std::unexpected(PublishError::InvalidEpoch);
		if (records.size() > transport::COMMAND_RECORDS_CAPACITY)
			return std::unexpected(PublishError::RecordBackpressure);
		if (payload.size() > transport::COMMAND_PAYLOAD_CAPACITY)
			return std::unexpected(PublishError::PayloadBackpressure);

		transport::RingControl &record_ring = view_.header().command_records;
		transport::RingControl &payload_ring = view_.header().command_payload;
		std::atomic_ref<std::uint32_t> record_producer(record_ring.producer_sequence);
		std::atomic_ref<std::uint32_t> record_consumer(record_ring.consumer_sequence);
		std::atomic_ref<std::uint32_t> payload_producer(payload_ring.producer_sequence);
		std::atomic_ref<std::uint32_t> payload_consumer(payload_ring.consumer_sequence);
		const std::uint32_t record_write = record_producer.load(std::memory_order_relaxed);
		const std::uint32_t record_read = record_consumer.load(std::memory_order_acquire);
		const std::uint32_t payload_write = payload_producer.load(std::memory_order_relaxed);
		const std::uint32_t payload_read = payload_consumer.load(std::memory_order_acquire);
		if (record_write - record_read > transport::COMMAND_RECORDS_CAPACITY
		    || records.size() > transport::COMMAND_RECORDS_CAPACITY - (record_write - record_read))
			return std::unexpected(PublishError::RecordBackpressure);
		if (payload_write - payload_read > transport::COMMAND_PAYLOAD_CAPACITY
		    || payload.size() > transport::COMMAND_PAYLOAD_CAPACITY - (payload_write - payload_read))
			return std::unexpected(PublishError::PayloadBackpressure);

		auto record_memory = view_.memory().subspan(
		    transport::COMMAND_RECORDS_OFFSET, transport::COMMAND_RECORDS_BYTES);
		for (std::size_t index = 0; index < records.size(); ++index) {
			const std::uint32_t slot = (record_write + static_cast<std::uint32_t>(index))
			                         % transport::COMMAND_RECORDS_CAPACITY;
			std::memcpy(record_memory.data() + slot * transport::COMMAND_RECORDS_RECORD_BYTES,
			            &records[index], sizeof(Record));
		}
		if (!payload.empty()) {
			auto payload_memory = view_.memory().subspan(
			    transport::COMMAND_PAYLOAD_OFFSET, transport::COMMAND_PAYLOAD_BYTES);
			const std::uint32_t first = std::min<std::uint32_t>(
			    static_cast<std::uint32_t>(payload.size()),
			    transport::COMMAND_PAYLOAD_CAPACITY
			        - (payload_write % transport::COMMAND_PAYLOAD_CAPACITY));
			std::memcpy(payload_memory.data() + (payload_write % transport::COMMAND_PAYLOAD_CAPACITY),
			            payload.data(), first);
			if (first < payload.size())
				std::memcpy(payload_memory.data(), payload.data() + first, payload.size() - first);
		}
		std::atomic_thread_fence(std::memory_order_release);
		payload_producer.store(payload_write + static_cast<std::uint32_t>(payload.size()),
		                       std::memory_order_release);
		record_producer.store(record_write + static_cast<std::uint32_t>(records.size()),
		                      std::memory_order_release);
		return record_write + static_cast<std::uint32_t>(records.size());
	}

private:
	transport::AbiView view_;
	std::uint32_t epoch_;
};

} // namespace diablo::mister::command
