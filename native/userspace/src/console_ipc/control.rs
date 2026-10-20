//! Opt-in PLC1 service, retaining ordinary console state outside control.
use super::{Error, Kind, Message, Registers};
use crate::session_control::{
    Action, App, Channel, Frame, Reply, Request, resumed_sequence, rpc::Exchange,
};

#[derive(Clone, Copy)]
enum Phase {
    Console,
    Send(Request),
    Result(Request),
    Ack(Reply),
    Failed,
}

pub struct Server {
    console: super::Server,
    phase: Phase,
    result: Option<Reply>,
}
struct Console<'a, C>(&'a mut C);
impl<C: Channel> super::Channel for Console<'_, C> {
    fn receive(&mut self) -> Result<Option<Message>, Error> {
        match self.0.receive()? {
            None => Ok(None),
            Some(Exchange::Console(message)) => Ok(Some(message)),
            _ => Err(Error::Wire),
        }
    }
    fn send(&mut self, message: Message) -> Result<bool, Error> {
        self.0.send(Exchange::Console(message))
    }
}
impl Default for Server {
    fn default() -> Self {
        Self::new()
    }
}
impl Server {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            console: super::Server::new(),
            phase: Phase::Console,
            result: None,
        }
    }
    /// False means no control slot is available; no request has been queued.
    #[inline]
    pub fn request(&mut self, app: App, action: Action, generation: u32) -> Result<bool, Error> {
        if matches!(self.phase, Phase::Failed) {
            return Err(Error::Transport);
        }
        if !matches!(self.phase, Phase::Console)
            || self.console.phase != super::Phase::Read
            || self.result.is_some()
        {
            return Ok(false);
        }
        let request = Request::new(self.console.sequence, app, action, generation)
            .and_then(|request| resumed_sequence(request.sequence()).map(|_| request));
        match request {
            Ok(request) => {
                self.phase = Phase::Send(request);
                Ok(true)
            }
            Err(error) => {
                self.phase = Phase::Failed;
                Err(error)
            }
        }
    }
    #[inline]
    pub fn take_result(&mut self) -> Option<Reply> {
        if matches!(self.phase, Phase::Failed) {
            None
        } else {
            self.result.take()
        }
    }
    /// One transport operation or one ordinary bounded device step per poll.
    #[inline(never)]
    pub fn poll(
        &mut self,
        port: &mut impl Registers,
        channel: &mut impl Channel,
    ) -> Result<bool, Error> {
        let result = self.step(port, channel);
        if result.is_err() {
            self.phase = Phase::Failed;
        }
        result
    }
    fn step(
        &mut self,
        port: &mut impl Registers,
        channel: &mut impl Channel,
    ) -> Result<bool, Error> {
        match self.phase {
            Phase::Console => return self.console.poll(port, &mut Console(channel)),
            Phase::Send(request) => {
                if channel.send(Exchange::Control(Frame::Request(request)))? {
                    self.phase = Phase::Result(request);
                }
            }
            Phase::Result(request) => {
                let Some(exchange) = channel.receive()? else {
                    return Ok(false);
                };
                let Exchange::Control(Frame::Reply(reply)) = exchange else {
                    return Err(Error::Wire);
                };
                if reply.request() != request {
                    return Err(Error::Sequence);
                }
                self.phase = Phase::Ack(reply);
            }
            Phase::Ack(reply) => {
                let resumed = resumed_sequence(reply.request().sequence())?;
                let ack = Message::new(Kind::Written, resumed - 1, &[])?;
                if channel.send(Exchange::Console(ack))? {
                    self.console.sequence = resumed;
                    self.console.phase = super::Phase::Idle;
                    self.result = Some(reply);
                    self.phase = Phase::Console;
                }
            }
            Phase::Failed => return Err(Error::Transport),
        }
        Ok(false)
    }
}

#[cfg(test)]
mod tests;
