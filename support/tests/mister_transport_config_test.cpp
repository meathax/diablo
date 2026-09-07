#include "mister_transport_config.hpp"

#include <cstdlib>
#include <iostream>

using diablo::mister::transport::ParseTransportRequest;
using diablo::mister::transport::TransportRequest;
using diablo::mister::transport::TransportRequestError;

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
	Require(ParseTransportRequest(nullptr) == TransportRequest::Disabled,
	        "unset transport request was not disabled");
	Require(ParseTransportRequest("") == TransportRequest::Disabled,
	        "empty transport request was not disabled");
	Require(ParseTransportRequest("0") == TransportRequest::Disabled
	            && ParseTransportRequest("false") == TransportRequest::Disabled,
	        "explicit disabled transport request was not disabled");
	Require(ParseTransportRequest("1") == TransportRequest::Enabled
	            && ParseTransportRequest("true") == TransportRequest::Enabled,
	        "explicit enabled transport request was not enabled");
	Require(ParseTransportRequest("yes") == TransportRequest::Invalid
	            && ParseTransportRequest("TRUE") == TransportRequest::Invalid,
	        "malformed transport request was accepted");
	Require(*TransportRequestError(TransportRequest::Invalid) != '\0',
	        "invalid transport request did not report an error");
	std::cout << "transport configuration checks passed\n";
}
