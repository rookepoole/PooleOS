//! Opt-in PLC1 client. Only an outstanding shell Read can yield to control.
use super::{Shell, applications::ApplicationCommands};
use crate::{
    console_ipc::{self, Error, Kind, Message},
    session_control::{Broker, Channel, Frame, Reply, Request, resumed_sequence, rpc::Exchange},
};

#[derive(Clone, Copy)]
enum Phase {
    Console,
    Process,
    Send(Reply),
    Ack(Reply),
    Failed,
}

pub struct Client<'a, C, P> {
    shell: Shell<ApplicationCommands<'a, C, P>>,
    broker: Broker,
    phase: Phase,
}

struct Console<'a, C> {
    channel: &'a mut C,
    control: Option<Request>,
}
impl<C: Channel> console_ipc::Channel for Console<'_, C> {
    fn receive(&mut self) -> Result<Option<Message>, Error> {
        match self.channel.receive()? {
            None => Ok(None),
            Some(Exchange::Console(message)) => Ok(Some(message)),
            Some(Exchange::Control(Frame::Request(request))) if self.control.is_none() => {
                self.control = Some(request);
                Ok(None)
            }
            _ => Err(Error::Wire),
        }
    }
    fn send(&mut self, message: Message) -> Result<bool, Error> {
        self.channel.send(Exchange::Console(message))
    }
}

impl<'a, C: console_ipc::rpc::Calls, P: crate::supervisor::Calls> Client<'a, C, P> {
    #[inline(always)]
    pub const fn new(commands: ApplicationCommands<'a, C, P>) -> Self {
        Self {
            shell: Shell::with_commands(commands),
            broker: Broker::new(),
            phase: Phase::Console,
        }
    }

    fn read_matches(&self, sequence: u64) -> bool {
        !self.shell.closed
            && self.shell.sequence == sequence
            && self.shell.pending == Some((Kind::Input, 0))
    }

    /// One transport operation or one bounded process-owner step per poll.
    #[inline(never)]
    pub fn poll(&mut self, channel: &mut impl Channel) -> Result<bool, Error> {
        let result = self.step(channel);
        if result.is_err() {
            self.phase = Phase::Failed;
        }
        result
    }

    fn step(&mut self, channel: &mut impl Channel) -> Result<bool, Error> {
        match self.phase {
            Phase::Console => {
                let mut console = Console {
                    channel,
                    control: None,
                };
                let closed = self.shell.poll(&mut console)?;
                if let Some(request) = console.control {
                    if !self.read_matches(request.sequence()) {
                        return Err(Error::Sequence);
                    }
                    resumed_sequence(request.sequence())?;
                    self.broker
                        .begin(request, self.shell.commands.process_owner())?;
                    self.phase = Phase::Process;
                }
                return Ok(closed);
            }
            Phase::Process => {
                if self.broker.poll(self.shell.commands.process_owner())? {
                    self.phase = Phase::Send(self.broker.reply().ok_or(Error::Sequence)?);
                }
            }
            Phase::Send(reply) => {
                if channel.send(Exchange::Control(Frame::Reply(reply)))? {
                    self.phase = Phase::Ack(reply);
                }
            }
            Phase::Ack(reply) => {
                let Some(exchange) = channel.receive()? else {
                    return Ok(false);
                };
                let sequence = reply.request().sequence();
                let resumed = resumed_sequence(sequence)?;
                let Exchange::Console(message) = exchange else {
                    return Err(Error::Wire);
                };
                if !self.read_matches(sequence)
                    || message.kind() != Kind::Written
                    || message.sequence() != resumed - 1
                {
                    return Err(Error::Sequence);
                }
                self.broker.acknowledge(sequence)?;
                self.shell.sequence = resumed;
                self.shell.pending = None;
                self.phase = Phase::Console;
            }
            Phase::Failed => return Err(Error::Transport),
        }
        Ok(false)
    }
}

#[cfg(test)]
mod tests;
