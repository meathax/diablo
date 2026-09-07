#pragma once

#include <cstring>

namespace diablo::mister::transport {

enum class TransportRequest {
	Disabled,
	Enabled,
	Invalid,
};

// Keep all launch paths on the same strict transport switch. In particular,
// a nonempty but malformed value must not select SDL dummy video while the
// adapter silently remains inactive.
[[nodiscard]] inline TransportRequest ParseTransportRequest(const char *value)
{
	if (value == nullptr || *value == '\0' || std::strcmp(value, "0") == 0
	    || std::strcmp(value, "false") == 0)
		return TransportRequest::Disabled;
	if (std::strcmp(value, "1") == 0 || std::strcmp(value, "true") == 0)
		return TransportRequest::Enabled;
	return TransportRequest::Invalid;
}

[[nodiscard]] inline const char *TransportRequestError(TransportRequest request)
{
	return request == TransportRequest::Invalid
	    ? "DIABLO_MISTER_TRANSPORT must be 0, false, 1 or true"
	    : "";
}

} // namespace diablo::mister::transport
