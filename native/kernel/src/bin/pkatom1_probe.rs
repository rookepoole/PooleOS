use std::ptr;
use std::sync::{Arc, Barrier};
use std::thread;

use poolekernel::atomics::{
    AtomicPtr, AtomicU32, AtomicU64, AtomicUsize, CompareExchangeOrder, LoadOrder, MAX_REFCOUNT,
    RefCount, RefCountError, RmwOrder, StoreOrder, classify_order_matrix,
};

const PUBLICATION_ROUNDS: u64 = 4096;
const COUNTER_THREADS: usize = 4;
const COUNTER_ROUNDS: u64 = 4096;
const CAS_ROUNDS: u64 = 1024;
const SEQCST_ROUNDS: u64 = 2048;

fn publication_litmus() -> (u64, u64) {
    let payload = Arc::new(AtomicU64::new(0));
    let ready = Arc::new(AtomicU64::new(0));
    let consumed = Arc::new(AtomicU64::new(0));

    let writer_payload = Arc::clone(&payload);
    let writer_ready = Arc::clone(&ready);
    let writer_consumed = Arc::clone(&consumed);
    let writer = thread::spawn(move || {
        for sequence in 1..=PUBLICATION_ROUNDS {
            while writer_consumed.load(LoadOrder::Acquire) != sequence - 1 {
                std::hint::spin_loop();
            }
            writer_payload.store(sequence, StoreOrder::Relaxed);
            writer_ready.store(sequence, StoreOrder::Release);
        }
    });

    let reader_payload = Arc::clone(&payload);
    let reader_ready = Arc::clone(&ready);
    let reader_consumed = Arc::clone(&consumed);
    let reader = thread::spawn(move || {
        let mut stale = 0u64;
        for sequence in 1..=PUBLICATION_ROUNDS {
            while reader_ready.load(LoadOrder::Acquire) != sequence {
                std::hint::spin_loop();
            }
            stale += u64::from(reader_payload.load(LoadOrder::Relaxed) != sequence);
            reader_consumed.store(sequence, StoreOrder::Release);
        }
        stale
    });

    writer.join().expect("publication writer");
    let stale = reader.join().expect("publication reader");
    (consumed.load(LoadOrder::Acquire), stale)
}

fn contended_operations() -> (u64, u64) {
    let counter = Arc::new(AtomicU64::new(0));
    let mut workers = Vec::new();
    for _ in 0..COUNTER_THREADS {
        let counter = Arc::clone(&counter);
        workers.push(thread::spawn(move || {
            for _ in 0..COUNTER_ROUNDS {
                counter.fetch_add(1, RmwOrder::Relaxed);
            }
        }));
    }
    for worker in workers {
        worker.join().expect("fetch-add worker");
    }

    let cas = Arc::new(AtomicU64::new(0));
    let mut cas_workers = Vec::new();
    for _ in 0..COUNTER_THREADS {
        let cas = Arc::clone(&cas);
        cas_workers.push(thread::spawn(move || {
            for _ in 0..CAS_ROUNDS {
                let mut current = cas.load(LoadOrder::Relaxed);
                loop {
                    match cas.compare_exchange_weak(
                        current,
                        current + 1,
                        CompareExchangeOrder::ACQ_REL,
                    ) {
                        Ok(_) => break,
                        Err(observed) => {
                            current = observed;
                            std::hint::spin_loop();
                        }
                    }
                }
            }
        }));
    }
    for worker in cas_workers {
        worker.join().expect("compare-exchange worker");
    }
    (
        counter.load(LoadOrder::Acquire),
        cas.load(LoadOrder::Acquire),
    )
}

fn seqcst_store_buffer_litmus() -> u64 {
    let x = Arc::new(AtomicU64::new(0));
    let y = Arc::new(AtomicU64::new(0));
    let left_observed = Arc::new(AtomicU64::new(0));
    let right_observed = Arc::new(AtomicU64::new(0));
    let barrier = Arc::new(Barrier::new(3));

    let left_x = Arc::clone(&x);
    let left_y = Arc::clone(&y);
    let left_result = Arc::clone(&left_observed);
    let left_barrier = Arc::clone(&barrier);
    let left = thread::spawn(move || {
        for _ in 0..SEQCST_ROUNDS {
            left_barrier.wait();
            left_x.store(1, StoreOrder::SeqCst);
            left_result.store(left_y.load(LoadOrder::SeqCst), StoreOrder::Relaxed);
            left_barrier.wait();
        }
    });

    let right_x = Arc::clone(&x);
    let right_y = Arc::clone(&y);
    let right_result = Arc::clone(&right_observed);
    let right_barrier = Arc::clone(&barrier);
    let right = thread::spawn(move || {
        for _ in 0..SEQCST_ROUNDS {
            right_barrier.wait();
            right_y.store(1, StoreOrder::SeqCst);
            right_result.store(right_x.load(LoadOrder::SeqCst), StoreOrder::Relaxed);
            right_barrier.wait();
        }
    });

    let mut forbidden = 0u64;
    for _ in 0..SEQCST_ROUNDS {
        x.store(0, StoreOrder::SeqCst);
        y.store(0, StoreOrder::SeqCst);
        left_observed.store(0, StoreOrder::Relaxed);
        right_observed.store(0, StoreOrder::Relaxed);
        barrier.wait();
        barrier.wait();
        forbidden += u64::from(
            left_observed.load(LoadOrder::Relaxed) == 0
                && right_observed.load(LoadOrder::Relaxed) == 0,
        );
    }
    left.join().expect("seqcst left worker");
    right.join().expect("seqcst right worker");
    forbidden
}

fn main() {
    let matrix = classify_order_matrix();
    assert_eq!(
        (
            matrix.load_orders,
            matrix.store_orders,
            matrix.rmw_orders,
            matrix.fence_orders,
            matrix.compare_exchange_pairs,
            matrix.rejected_combinations,
        ),
        (3, 3, 5, 4, 9, 11)
    );
    println!("PKATOM1:TYPES PASS integer=u32,u64,usize pointer=typed atomics=4 target=x86_64");
    println!(
        "PKATOM1:ORDERS PASS load={} store={} rmw={} fence={} cas_pairs={} invalid_rejected={}",
        matrix.load_orders,
        matrix.store_orders,
        matrix.rmw_orders,
        matrix.fence_orders,
        matrix.compare_exchange_pairs,
        matrix.rejected_combinations,
    );

    let value = AtomicU64::new(7);
    value.store(9, StoreOrder::Release);
    let exchanged = value.exchange(11, RmwOrder::AcqRel);
    let compared = value
        .compare_exchange(11, 13, CompareExchangeOrder::ACQ_REL)
        .expect("compare-exchange");
    let added = value.fetch_add(5, RmwOrder::Relaxed);
    let subtracted = value.fetch_sub(2, RmwOrder::Acquire);
    let ored = value.fetch_or(0x20, RmwOrder::Release);
    let xored = value.fetch_xor(0x10, RmwOrder::SeqCst);
    let anded = value.fetch_and(0x1f, RmwOrder::AcqRel);
    let small = AtomicU32::new(0);
    assert_eq!(small.fetch_set_bit(31, RmwOrder::AcqRel), Ok(false));
    assert_eq!(small.fetch_clear_bit(31, RmwOrder::AcqRel), Ok(true));
    let word = AtomicUsize::new(3);
    assert_eq!(word.fetch_add(2, RmwOrder::Relaxed), 3);
    assert_eq!(
        (exchanged, compared, added, subtracted, ored, xored, anded),
        (9, 11, 13, 18, 16, 48, 32)
    );
    println!(
        "PKATOM1:OPS PASS exchange_old={} cas_old={} add_old={} sub_old={} or_old={} xor_old={} and_old={} final={} bit_set_clear=1 usize_final={}",
        exchanged,
        compared,
        added,
        subtracted,
        ored,
        xored,
        anded,
        value.load(LoadOrder::Acquire),
        word.load(LoadOrder::Acquire),
    );

    let mut first = 0x1111u64;
    let mut second = 0x2222u64;
    let pointer = AtomicPtr::new(&mut first);
    let first_address = &mut first as *mut u64;
    let second_address = &mut second as *mut u64;
    assert_eq!(
        pointer.exchange(second_address, RmwOrder::AcqRel),
        first_address
    );
    assert_eq!(
        pointer.compare_exchange(
            second_address,
            ptr::null_mut(),
            CompareExchangeOrder::ACQ_REL
        ),
        Ok(second_address)
    );
    assert!(pointer.load(LoadOrder::Acquire).is_null());
    println!("PKATOM1:POINTER PASS typed=1 exchange=1 compare_exchange=1 null_terminal=1");

    let count = RefCount::try_new(1).expect("refcount");
    assert_eq!(count.acquire(), Ok(2));
    assert_eq!(count.release().expect("release one").remaining, 1);
    assert!(count.release().expect("release zero").became_zero);
    assert_eq!(count.release(), Err(RefCountError::Underflow));
    let maximum = RefCount::try_new(MAX_REFCOUNT).expect("maximum refcount");
    assert_eq!(maximum.acquire(), Err(RefCountError::Overflow));
    println!(
        "PKATOM1:REFCOUNT PASS start=1 peak=2 terminal=0 overflow_rejected=1 underflow_rejected=1 max={}",
        MAX_REFCOUNT
    );

    let (published, stale) = publication_litmus();
    assert_eq!((published, stale), (PUBLICATION_ROUNDS, 0));
    println!(
        "PKATOM1:PUBLICATION PASS rounds={} published={} stale={} release_acquire=1",
        PUBLICATION_ROUNDS, published, stale
    );

    let (fetch_add_final, cas_final) = contended_operations();
    assert_eq!(fetch_add_final, COUNTER_THREADS as u64 * COUNTER_ROUNDS);
    assert_eq!(cas_final, COUNTER_THREADS as u64 * CAS_ROUNDS);
    println!(
        "PKATOM1:CONTENTION PASS threads={} fetch_add_rounds={} fetch_add_final={} cas_rounds={} cas_final={} lost=0",
        COUNTER_THREADS, COUNTER_ROUNDS, fetch_add_final, CAS_ROUNDS, cas_final
    );

    let forbidden = seqcst_store_buffer_litmus();
    assert_eq!(forbidden, 0);
    println!(
        "PKATOM1:SEQCST PASS rounds={} both_zero_forbidden={} observed_forbidden={}",
        SEQCST_ROUNDS, SEQCST_ROUNDS, forbidden
    );
}
