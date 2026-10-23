//! Executed service steps; protocol state commits only after successful transport.
#![forbid(unsafe_code)]
use crate::protocol::{Counter, Error as ProtocolError, Init, Message};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Transport,
    Protocol(ProtocolError),
}
pub trait Channel {
    fn send(&mut self, message: Message) -> Result<(), Error>;
    fn receive(&mut self) -> Result<Message, Error>;
}
pub fn init_step(state: &mut Init, channel: &mut impl Channel) -> Result<(), Error> {
    channel.send(state.request().map_err(Error::Protocol)?)?;
    state.accept(channel.receive()?).map_err(Error::Protocol)
}
pub fn counter_step(state: &mut Counter, channel: &mut impl Channel) -> Result<(), Error> {
    let (next, reply) = state.prepare(channel.receive()?).map_err(Error::Protocol)?;
    channel.send(reply)?;
    *state = next;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::Kind;
    struct Mock {
        incoming: Message,
        outgoing: Option<Message>,
        send_fail: bool,
        receive_fail: bool,
    }
    impl Channel for Mock {
        fn send(&mut self, message: Message) -> Result<(), Error> {
            if self.send_fail {
                return Err(Error::Transport);
            }
            self.outgoing = Some(message);
            Ok(())
        }
        fn receive(&mut self) -> Result<Message, Error> {
            if self.receive_fail {
                Err(Error::Transport)
            } else {
                Ok(self.incoming)
            }
        }
    }
    fn mock(message: Message) -> Mock {
        Mock {
            incoming: message,
            outgoing: None,
            send_fail: false,
            receive_fail: false,
        }
    }
    #[test]
    fn counter_commits_only_after_reply_is_sent() {
        let request = Init::new().request().unwrap();
        let mut state = Counter::new();
        let mut io = mock(request);
        io.send_fail = true;
        assert_eq!(counter_step(&mut state, &mut io), Err(Error::Transport));
        assert_eq!(state, Counter::new());
        io.send_fail = false;
        assert_eq!(counter_step(&mut state, &mut io), Ok(()));
        assert_eq!(
            io.outgoing,
            Some(Message {
                kind: Kind::Ready,
                sequence: 0,
                value: 0
            })
        );
        assert!(state.prepare(request).is_err());
    }
    #[test]
    fn init_transport_failures_preserve_state() {
        for (send_fail, receive_fail) in [(true, false), (false, true)] {
            let mut state = Init::new();
            let mut io = mock(Message {
                kind: Kind::Ready,
                sequence: 0,
                value: 0,
            });
            io.send_fail = send_fail;
            io.receive_fail = receive_fail;
            assert_eq!(init_step(&mut state, &mut io), Err(Error::Transport));
            assert_eq!(state, Init::new());
        }
    }
    #[test]
    fn invalid_counter_request_is_never_sent_or_committed() {
        let mut state = Counter::new();
        let mut io = mock(Message {
            kind: Kind::Advance,
            sequence: 1,
            value: 1,
        });
        assert!(counter_step(&mut state, &mut io).is_err());
        assert!(io.outgoing.is_none());
        assert_eq!(state, Counter::new());
    }
    #[test]
    fn init_accepts_only_expected_reply_after_sending_its_request() {
        let mut state = Init::new();
        let mut io = mock(Message {
            kind: Kind::Ready,
            sequence: 0,
            value: 0,
        });
        init_step(&mut state, &mut io).unwrap();
        assert_eq!(io.outgoing, Some(Init::new().request().unwrap()));
        assert_eq!(state.request().unwrap().kind, Kind::Advance);
        let old = state;
        assert!(init_step(&mut state, &mut io).is_err());
        assert_eq!(state, old);
    }
}
