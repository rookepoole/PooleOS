use super::*;
use std::{vec, vec::Vec};
fn evaluate(kind: Kind, data: &[u8], chunk: usize) -> Result<[i64; 4], u8> {
    let mut value = Accumulator::new(kind);
    for bytes in data.chunks(chunk) {
        value.push(bytes)?;
    }
    value.finish()
}
#[test]
fn text_counts_are_invariant_across_every_chunk_size() {
    let data = b"  hello\tworld\r\nlast word";
    for chunk in 1..=data.len() {
        assert_eq!(evaluate(Kind::Text, data, chunk), Ok([24, 4, 1, 0]));
    }
    assert_eq!(evaluate(Kind::Text, b"", 1), Ok([0; 4]));
    assert_eq!(evaluate(Kind::Text, b"\r\n\n\t", 1), Ok([4, 0, 2, 0]));
}
#[test]
fn numeric_rows_support_header_crlf_extremes_and_unterminated_last_row() {
    for data in [
        &b"value\r\n3\r\n5\n-8\r\n13\n21"[..],
        &b"3\n5\n-8\n13\n21\n"[..],
    ] {
        for chunk in 1..=data.len() {
            assert_eq!(evaluate(Kind::Numbers, data, chunk), Ok([5, 34, -8, 21]));
        }
    }
    assert_eq!(
        evaluate(Kind::Numbers, b"-2147483648\r\n2147483647", 1),
        Ok([2, -1, -2147483648, 2147483647])
    );
    assert_eq!(evaluate(Kind::Numbers, b"value\r\n", 1), Ok([0; 4]));
    assert_eq!(evaluate(Kind::Numbers, b"", 1), Ok([0; 4]));
}
#[test]
fn malformed_numeric_inputs_fail_without_partial_success() {
    for data in [
        &b"2147483648"[..],
        b"-2147483649",
        b"9999999999",
        b"00000000000",
        b"1\r",
        b"1\r2",
        b"1\r\r\n",
        b"+1",
        b"-",
        b"1,2",
        b"1.0",
        b"1e2",
        b" 1",
        b"1 ",
        b"\n",
        b"1\n\n",
        b"1\nvalue",
        b"value\nvalue",
        b"VALUE",
        b"NaN",
        b"1\0",
        b"\xff",
    ] {
        for chunk in 1..=data.len() {
            assert_eq!(
                evaluate(Kind::Numbers, data, chunk),
                Err(INVALID_DATA),
                "{data:?}/{chunk}"
            );
        }
    }
}
#[test]
fn text_controls_and_non_ascii_reject_and_failure_is_terminal() {
    for byte in (0..=255).filter(|b| !matches!(b, 32..=126 | b'\r' | b'\n' | b'\t')) {
        let mut a = Accumulator::new(Kind::Text);
        assert_eq!(a.push(&[byte]), Err(INVALID_DATA));
        assert_eq!(a.push(b"valid"), Err(INVALID_DATA));
        assert_eq!(a.finish(), Err(INVALID_DATA));
    }
}
#[test]
fn file_and_row_limits_are_inclusive_and_completion_is_single_use() {
    assert_eq!(
        evaluate(Kind::Text, &vec![b'x'; MAX_FILE_BYTES as usize], 39),
        Ok([4096, 1, 0, 0])
    );
    assert_eq!(
        evaluate(Kind::Text, &vec![b'x'; MAX_FILE_BYTES as usize + 1], 40),
        Err(LIMIT)
    );
    let rows: Vec<u8> = (0..MAX_ROWS).flat_map(|_| *b"-1\n").collect();
    assert_eq!(evaluate(Kind::Numbers, &rows, 7), Ok([256, -256, -1, -1]));
    assert_eq!(
        evaluate(Kind::Numbers, &[rows, b"2\n".to_vec()].concat(), 7),
        Err(LIMIT)
    );
    let mut a = Accumulator::new(Kind::Text);
    assert!(a.finish().is_ok());
    assert_eq!(a.finish(), Err(INVALID_DATA));
    assert_eq!(a.push(b"x"), Err(INVALID_DATA));
}
#[test]
fn independent_integer_oracle_matches_varied_signed_datasets() {
    for seed in 0i64..64 {
        let values: Vec<i32> = (0..31)
            .map(|i| ((seed * 7919 + i * 104729) % 200000 - 100000) as i32)
            .collect();
        let text = values
            .iter()
            .map(|v| std::format!("{v}\r\n"))
            .collect::<std::string::String>();
        let expected = [
            values.len() as i64,
            values.iter().map(|&v| i64::from(v)).sum(),
            i64::from(*values.iter().min().unwrap()),
            i64::from(*values.iter().max().unwrap()),
        ];
        for chunk in [1, 7, 40, 63] {
            assert_eq!(
                evaluate(Kind::Numbers, text.as_bytes(), chunk),
                Ok(expected)
            );
        }
    }
}
