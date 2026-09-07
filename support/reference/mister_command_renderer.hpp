#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>

namespace diablo::mister::command {

// The command ring is intentionally fixed width so the FPGA can fetch one
// record with four 64-bit reads and validate it before touching a render target.
enum class Opcode : std::uint32_t {
	FillRect = 1,
	CopyRect = 2,
	End = 0xffff,
};

struct alignas(8) Record {
	std::uint32_t opcode;
	std::uint32_t flags;
	std::int32_t x;
	std::int32_t y;
	std::int32_t width;
	std::int32_t height;
	std::uint32_t payload_offset;
	std::uint32_t payload_bytes;
};
static_assert(sizeof(Record) == 32);
static_assert(alignof(Record) == 8);

inline constexpr std::size_t kMaxRecords = 2048;

class Buffer {
public:
	static constexpr std::size_t MaxRecords = kMaxRecords;

	void Reset() { count_ = 0; }

	[[nodiscard]] std::size_t size() const { return count_; }
	[[nodiscard]] std::span<const Record> records() const
	{
		return { records_.data(), count_ };
	}

	[[nodiscard]] bool FillRect(std::int32_t x, std::int32_t y, std::int32_t width,
	                            std::int32_t height, std::uint8_t color)
	{
		return FillRectToSlot(x, y, width, height, color, 0);
	}

	[[nodiscard]] bool FillRectToSlot(std::int32_t x, std::int32_t y, std::int32_t width,
	                                  std::int32_t height, std::uint8_t color,
	                                  std::uint32_t target_slot)
	{
		if (target_slot >= 3) return false;
		return Append({ static_cast<std::uint32_t>(Opcode::FillRect),
		                (target_slot << 8U) | color,
		                x, y, width, height, 0, 0 });
	}

	[[nodiscard]] bool CopyRect(std::int32_t x, std::int32_t y, std::int32_t width,
	                            std::int32_t height, std::int32_t source_x,
	                            std::int32_t source_y)
	{
		return CopyRectToSlot(x, y, width, height, source_x, source_y, 0);
	}

	[[nodiscard]] bool CopyRectToSlot(std::int32_t x, std::int32_t y, std::int32_t width,
	                                  std::int32_t height, std::int32_t source_x,
	                                  std::int32_t source_y, std::uint32_t target_slot)
	{
		if (target_slot >= 3) return false;
		const auto packed_source = PackCoordinates(source_x, source_y);
		return Append({ static_cast<std::uint32_t>(Opcode::CopyRect), target_slot << 8U,
		                x, y, width, height, packed_source, 0 });
	}

	[[nodiscard]] bool End(std::uint64_t fence = 0)
	{
		return Append({ static_cast<std::uint32_t>(Opcode::End), 0, 0, 0, 0, 0,
		                static_cast<std::uint32_t>(fence >> 32U),
		                static_cast<std::uint32_t>(fence) });
	}

private:
	static constexpr std::uint32_t PackCoordinates(std::int32_t x, std::int32_t y)
	{
		return static_cast<std::uint32_t>(static_cast<std::uint16_t>(x))
		     | static_cast<std::uint32_t>(static_cast<std::uint16_t>(y)) << 16U;
	}

	[[nodiscard]] bool Append(Record record)
	{
		if (count_ == records_.size()) return false;
		records_[count_++] = record;
		return true;
	}

	std::array<Record, kMaxRecords> records_ {};
	std::size_t count_ = 0;
};

class SoftwareRenderer {
public:
	SoftwareRenderer(std::span<std::uint8_t> pixels, std::size_t pitch,
	                 std::int32_t width, std::int32_t height)
		: pixels_(pixels)
		, pitch_(pitch)
		, width_(width)
		, height_(height)
	{
	}

	[[nodiscard]] bool Execute(std::span<const Record> records)
	{
		if (width_ < 0 || height_ < 0
		    || pitch_ < static_cast<std::size_t>(width_))
			return false;
		const std::size_t rows = static_cast<std::size_t>(height_);
		if (rows != 0 && pitch_ > pixels_.size() / rows)
			return false;
		for (const Record &record : records) {
			switch (static_cast<Opcode>(record.opcode)) {
			case Opcode::FillRect:
				Fill(record);
				break;
			case Opcode::CopyRect:
				if (!Copy(record)) return false;
				break;
			case Opcode::End:
				return true;
			default:
				return false;
			}
		}
		return true;
	}

private:
	struct Rect {
		std::int32_t x;
		std::int32_t y;
		std::int32_t width;
		std::int32_t height;
	};

	[[nodiscard]] bool Clip(Rect &destination, Rect &source) const
	{
		if (destination.width <= 0 || destination.height <= 0) return false;
		if (source.width != destination.width || source.height != destination.height)
			return false;
		using Wide = std::int64_t;
		const Wide destination_x = destination.x;
		const Wide destination_y = destination.y;
		const Wide source_x = source.x;
		const Wide source_y = source.y;
		const Wide width = destination.width;
		const Wide height = destination.height;
		const Wide left = std::max({ Wide { 0 }, -destination_x, -source_x });
		const Wide top = std::max({ Wide { 0 }, -destination_y, -source_y });
		const Wide right = std::min({ width,
		                              static_cast<Wide>(width_) - destination_x,
		                              static_cast<Wide>(width_) - source_x });
		const Wide bottom = std::min({ height,
		                               static_cast<Wide>(height_) - destination_y,
		                               static_cast<Wide>(height_) - source_y });
		if (right <= left || bottom <= top) return false;
		destination.x = static_cast<std::int32_t>(destination_x + left);
		destination.y = static_cast<std::int32_t>(destination_y + top);
		source.x = static_cast<std::int32_t>(source_x + left);
		source.y = static_cast<std::int32_t>(source_y + top);
		destination.width = static_cast<std::int32_t>(right - left);
		destination.height = static_cast<std::int32_t>(bottom - top);
		source.width = destination.width;
		source.height = destination.height;
		return true;
	}

	void Fill(const Record &record)
	{
		using Wide = std::int64_t;
		Rect rect { record.x, record.y, record.width, record.height };
		const Wide left = std::max(Wide { 0 }, static_cast<Wide>(rect.x));
		const Wide top = std::max(Wide { 0 }, static_cast<Wide>(rect.y));
		const Wide right = std::min(static_cast<Wide>(width_),
		                             static_cast<Wide>(rect.x) + rect.width);
		const Wide bottom = std::min(static_cast<Wide>(height_),
		                              static_cast<Wide>(rect.y) + rect.height);
		if (right <= left || bottom <= top) return;
		for (Wide y = top; y < bottom; ++y)
			std::fill(pixels_.begin() + static_cast<std::size_t>(y) * pitch_ + static_cast<std::size_t>(left),
			          pixels_.begin() + static_cast<std::size_t>(y) * pitch_ + static_cast<std::size_t>(right),
			          static_cast<std::uint8_t>(record.flags & 0xffU));
	}

	[[nodiscard]] bool Copy(const Record &record)
	{
		Rect destination { record.x, record.y, record.width, record.height };
		Rect source { static_cast<std::int16_t>(record.payload_offset & 0xffffU),
		              static_cast<std::int16_t>(record.payload_offset >> 16U),
		              record.width, record.height };
		if (!Clip(destination, source)) return true;
		const bool bottom_up = destination.y > source.y;
		for (std::int32_t row = 0; row < destination.height; ++row) {
			const std::int32_t offset = bottom_up ? destination.height - 1 - row : row;
			auto *destination_row = pixels_.data()
			                     + static_cast<std::size_t>(destination.y + offset) * pitch_
			                     + destination.x;
			const auto *source_row = pixels_.data()
			                   + static_cast<std::size_t>(source.y + offset) * pitch_
			                   + source.x;
			std::memmove(destination_row, source_row,
			            static_cast<std::size_t>(destination.width));
		}
		return true;
	}

	std::span<std::uint8_t> pixels_;
	std::size_t pitch_;
	std::int32_t width_;
	std::int32_t height_;
};

} // namespace diablo::mister::command
