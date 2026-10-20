//! Explicit PCS1/PLC1 transport. Legacy PCS1 transport remains console-only.
use super::{Frame, Request};
use crate::console_ipc::{Error, Kind, Message, Peer, rpc};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Exchange {
    Console(Message),
    Control(Frame),
}
impl Exchange {
    #[inline]
    pub fn sequence(self) -> u64 {
        match self {
            Self::Console(message) => message.sequence(),
            Self::Control(Frame::Request(request)) => request.sequence(),
            Self::Control(Frame::Reply(reply)) => reply.request().sequence(),
        }
    }
    #[inline]
    fn encode(self) -> [u8; super::BYTES] {
        match self {
            Self::Console(message) => message.encode(),
            Self::Control(frame) => frame.encode(),
        }
    }
    #[inline]
    fn decode(wire: &[u8]) -> Result<Self, Error> {
        match wire.get(..4) {
            Some(b"PCS1") => Message::decode(wire).map(Self::Console),
            Some(b"PLC1") => Frame::decode(wire).map(Self::Control),
            _ => Err(Error::Wire),
        }
    }
    #[inline]
    fn from_server(self) -> bool {
        match self {
            Self::Console(message) => {
                matches!(message.kind(), Kind::Input | Kind::Written | Kind::Closed)
            }
            Self::Control(Frame::Request(_)) => true,
            Self::Control(Frame::Reply(_)) => false,
        }
    }
}

/// A console service sends control requests; the process-owning shell replies.
/// The session layer must additionally bind them to its outstanding Read/ack.
pub struct Transport {
    rpc: rpc::Transport,
    server: bool,
    failed: bool,
}
impl Transport {
    #[inline]
    pub fn new(endpoint: u64, peer: Peer, server: bool) -> Self {
        Self {
            rpc: rpc::Transport::new(endpoint, peer, server),
            server,
            failed: false,
        }
    }
    #[inline(always)]
    pub fn send(&mut self, exchange: Exchange, calls: &mut impl rpc::Calls) -> Result<bool, Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        if exchange.from_server() != self.server {
            self.failed = true;
            return Err(Error::Wire);
        }
        let result = self.rpc.send_encoded(exchange.encode(), calls);
        self.failed = result.is_err();
        result
    }
    #[inline(always)]
    pub fn receive(&mut self, calls: &mut impl rpc::Calls) -> Result<Option<Exchange>, Error> {
        if self.failed {
            return Err(Error::Transport);
        }
        let result = self.rpc.receive_with(calls, |wire| {
            let exchange = Exchange::decode(wire)?;
            if exchange.from_server() == self.server {
                return Err(Error::Wire);
            }
            Ok(exchange)
        });
        self.failed = result.is_err();
        result
    }
}

/// Owns the explicit protocol mode and its syscall adapter for one peer.
pub struct Connection<C> {
    transport: Transport,
    calls: C,
}
impl<C: rpc::Calls> Connection<C> {
    #[inline]
    pub fn new(endpoint: u64, peer: Peer, server: bool, calls: C) -> Self {
        Self {
            transport: Transport::new(endpoint, peer, server),
            calls,
        }
    }
}
impl<C: rpc::Calls> super::Channel for Connection<C> {
    // Share bounded transport steps between console and control state machines.
    #[inline(never)]
    fn send(&mut self, exchange: Exchange) -> Result<bool, Error> {
        self.transport.send(exchange, &mut self.calls)
    }
    #[inline(never)]
    fn receive(&mut self) -> Result<Option<Exchange>, Error> {
        self.transport.receive(&mut self.calls)
    }
}

/// No raw endpoint or process authority is carried by a control request.
impl From<Request> for Exchange {
    #[inline]
    fn from(request: Request) -> Self {
        Self::Control(Frame::Request(request))
    }
}

#[cfg(test)]
mod tests;
