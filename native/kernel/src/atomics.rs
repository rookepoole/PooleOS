use core::convert::TryFrom;
use core::hint::spin_loop;
use core::sync::atomic::{
    AtomicPtr as CoreAtomicPtr, AtomicU32 as CoreAtomicU32, AtomicU64 as CoreAtomicU64,
    AtomicUsize as CoreAtomicUsize, Ordering, compiler_fence as core_compiler_fence,
    fence as core_fence,
};

#[cfg(not(all(
    target_has_atomic = "32",
    target_has_atomic = "64",
    target_has_atomic = "ptr"
)))]
compile_error!("PKATOM1 requires native 32-bit, 64-bit, and pointer atomics");

pub const CONTRACT_ID: &str = "PKATOM1";
pub const MAX_REFCOUNT: u32 = u32::MAX - 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum MemoryOrder {
    Relaxed = 0,
    Acquire = 1,
    Release = 2,
    AcqRel = 3,
    SeqCst = 4,
}

impl MemoryOrder {
    pub const ALL: [Self; 5] = [
        Self::Relaxed,
        Self::Acquire,
        Self::Release,
        Self::AcqRel,
        Self::SeqCst,
    ];
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OrderError {
    InvalidLoad,
    InvalidStore,
    InvalidFence,
    CompareExchangeFailureStrongerThanSuccess,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum LoadOrder {
    Relaxed = 0,
    Acquire = 1,
    SeqCst = 2,
}

impl LoadOrder {
    #[inline(always)]
    const fn as_core(self) -> Ordering {
        match self {
            Self::Relaxed => Ordering::Relaxed,
            Self::Acquire => Ordering::Acquire,
            Self::SeqCst => Ordering::SeqCst,
        }
    }
}

impl TryFrom<MemoryOrder> for LoadOrder {
    type Error = OrderError;

    fn try_from(value: MemoryOrder) -> Result<Self, Self::Error> {
        match value {
            MemoryOrder::Relaxed => Ok(Self::Relaxed),
            MemoryOrder::Acquire => Ok(Self::Acquire),
            MemoryOrder::SeqCst => Ok(Self::SeqCst),
            MemoryOrder::Release | MemoryOrder::AcqRel => Err(OrderError::InvalidLoad),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum StoreOrder {
    Relaxed = 0,
    Release = 1,
    SeqCst = 2,
}

impl StoreOrder {
    #[inline(always)]
    const fn as_core(self) -> Ordering {
        match self {
            Self::Relaxed => Ordering::Relaxed,
            Self::Release => Ordering::Release,
            Self::SeqCst => Ordering::SeqCst,
        }
    }
}

impl TryFrom<MemoryOrder> for StoreOrder {
    type Error = OrderError;

    fn try_from(value: MemoryOrder) -> Result<Self, Self::Error> {
        match value {
            MemoryOrder::Relaxed => Ok(Self::Relaxed),
            MemoryOrder::Release => Ok(Self::Release),
            MemoryOrder::SeqCst => Ok(Self::SeqCst),
            MemoryOrder::Acquire | MemoryOrder::AcqRel => Err(OrderError::InvalidStore),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum RmwOrder {
    Relaxed = 0,
    Acquire = 1,
    Release = 2,
    AcqRel = 3,
    SeqCst = 4,
}

impl RmwOrder {
    pub const ALL: [Self; 5] = [
        Self::Relaxed,
        Self::Acquire,
        Self::Release,
        Self::AcqRel,
        Self::SeqCst,
    ];

    #[inline(always)]
    const fn as_core(self) -> Ordering {
        match self {
            Self::Relaxed => Ordering::Relaxed,
            Self::Acquire => Ordering::Acquire,
            Self::Release => Ordering::Release,
            Self::AcqRel => Ordering::AcqRel,
            Self::SeqCst => Ordering::SeqCst,
        }
    }
}

impl From<MemoryOrder> for RmwOrder {
    fn from(value: MemoryOrder) -> Self {
        match value {
            MemoryOrder::Relaxed => Self::Relaxed,
            MemoryOrder::Acquire => Self::Acquire,
            MemoryOrder::Release => Self::Release,
            MemoryOrder::AcqRel => Self::AcqRel,
            MemoryOrder::SeqCst => Self::SeqCst,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum FenceOrder {
    Acquire = 0,
    Release = 1,
    AcqRel = 2,
    SeqCst = 3,
}

impl FenceOrder {
    #[inline(always)]
    const fn as_core(self) -> Ordering {
        match self {
            Self::Acquire => Ordering::Acquire,
            Self::Release => Ordering::Release,
            Self::AcqRel => Ordering::AcqRel,
            Self::SeqCst => Ordering::SeqCst,
        }
    }
}

impl TryFrom<MemoryOrder> for FenceOrder {
    type Error = OrderError;

    fn try_from(value: MemoryOrder) -> Result<Self, Self::Error> {
        match value {
            MemoryOrder::Acquire => Ok(Self::Acquire),
            MemoryOrder::Release => Ok(Self::Release),
            MemoryOrder::AcqRel => Ok(Self::AcqRel),
            MemoryOrder::SeqCst => Ok(Self::SeqCst),
            MemoryOrder::Relaxed => Err(OrderError::InvalidFence),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CompareExchangeOrder {
    success: RmwOrder,
    failure: LoadOrder,
}

impl CompareExchangeOrder {
    pub const fn new(success: RmwOrder, failure: LoadOrder) -> Result<Self, OrderError> {
        let valid = match success {
            RmwOrder::Relaxed => matches!(failure, LoadOrder::Relaxed),
            RmwOrder::Acquire => matches!(failure, LoadOrder::Relaxed | LoadOrder::Acquire),
            RmwOrder::Release => matches!(failure, LoadOrder::Relaxed),
            RmwOrder::AcqRel => matches!(failure, LoadOrder::Relaxed | LoadOrder::Acquire),
            RmwOrder::SeqCst => true,
        };
        if valid {
            Ok(Self { success, failure })
        } else {
            Err(OrderError::CompareExchangeFailureStrongerThanSuccess)
        }
    }

    pub const RELAXED: Self = Self {
        success: RmwOrder::Relaxed,
        failure: LoadOrder::Relaxed,
    };
    pub const ACQUIRE: Self = Self {
        success: RmwOrder::Acquire,
        failure: LoadOrder::Acquire,
    };
    pub const RELEASE: Self = Self {
        success: RmwOrder::Release,
        failure: LoadOrder::Relaxed,
    };
    pub const ACQ_REL: Self = Self {
        success: RmwOrder::AcqRel,
        failure: LoadOrder::Acquire,
    };
    pub const SEQ_CST: Self = Self {
        success: RmwOrder::SeqCst,
        failure: LoadOrder::SeqCst,
    };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct OrderMatrix {
    pub load_orders: u8,
    pub store_orders: u8,
    pub rmw_orders: u8,
    pub fence_orders: u8,
    pub compare_exchange_pairs: u8,
    pub rejected_combinations: u8,
}

pub fn classify_order_matrix() -> OrderMatrix {
    let mut load_orders = 0u8;
    let mut store_orders = 0u8;
    let mut fence_orders = 0u8;
    let mut compare_exchange_pairs = 0u8;
    for order in MemoryOrder::ALL {
        load_orders += u8::from(LoadOrder::try_from(order).is_ok());
        store_orders += u8::from(StoreOrder::try_from(order).is_ok());
        fence_orders += u8::from(FenceOrder::try_from(order).is_ok());
    }
    for success in RmwOrder::ALL {
        for failure in [LoadOrder::Relaxed, LoadOrder::Acquire, LoadOrder::SeqCst] {
            compare_exchange_pairs += u8::from(CompareExchangeOrder::new(success, failure).is_ok());
        }
    }
    OrderMatrix {
        load_orders,
        store_orders,
        rmw_orders: RmwOrder::ALL.len() as u8,
        fence_orders,
        compare_exchange_pairs,
        rejected_combinations: (5 - load_orders)
            + (5 - store_orders)
            + (5 - fence_orders)
            + (15 - compare_exchange_pairs),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BitIndexError;

macro_rules! integer_atomic {
    ($name:ident, $core:ident, $value:ty) => {
        #[repr(transparent)]
        pub struct $name {
            value: $core,
        }

        impl $name {
            pub const fn new(value: $value) -> Self {
                Self {
                    value: $core::new(value),
                }
            }

            #[inline(always)]
            pub fn load(&self, order: LoadOrder) -> $value {
                self.value.load(order.as_core())
            }

            #[inline(always)]
            pub fn store(&self, value: $value, order: StoreOrder) {
                self.value.store(value, order.as_core());
            }

            #[inline(always)]
            pub fn exchange(&self, value: $value, order: RmwOrder) -> $value {
                self.value.swap(value, order.as_core())
            }

            #[inline(always)]
            pub fn compare_exchange(
                &self,
                current: $value,
                new: $value,
                order: CompareExchangeOrder,
            ) -> Result<$value, $value> {
                self.value.compare_exchange(
                    current,
                    new,
                    order.success.as_core(),
                    order.failure.as_core(),
                )
            }

            #[inline(always)]
            pub fn compare_exchange_weak(
                &self,
                current: $value,
                new: $value,
                order: CompareExchangeOrder,
            ) -> Result<$value, $value> {
                self.value.compare_exchange_weak(
                    current,
                    new,
                    order.success.as_core(),
                    order.failure.as_core(),
                )
            }

            #[inline(always)]
            pub fn fetch_add(&self, value: $value, order: RmwOrder) -> $value {
                self.value.fetch_add(value, order.as_core())
            }

            #[inline(always)]
            pub fn fetch_sub(&self, value: $value, order: RmwOrder) -> $value {
                self.value.fetch_sub(value, order.as_core())
            }

            #[inline(always)]
            pub fn fetch_and(&self, value: $value, order: RmwOrder) -> $value {
                self.value.fetch_and(value, order.as_core())
            }

            #[inline(always)]
            pub fn fetch_or(&self, value: $value, order: RmwOrder) -> $value {
                self.value.fetch_or(value, order.as_core())
            }

            #[inline(always)]
            pub fn fetch_xor(&self, value: $value, order: RmwOrder) -> $value {
                self.value.fetch_xor(value, order.as_core())
            }

            #[inline(always)]
            pub fn fetch_set_bit(&self, bit: u32, order: RmwOrder) -> Result<bool, BitIndexError> {
                if bit >= <$value>::BITS {
                    return Err(BitIndexError);
                }
                let mask = (1 as $value) << bit;
                Ok(self.fetch_or(mask, order) & mask != 0)
            }

            #[inline(always)]
            pub fn fetch_clear_bit(
                &self,
                bit: u32,
                order: RmwOrder,
            ) -> Result<bool, BitIndexError> {
                if bit >= <$value>::BITS {
                    return Err(BitIndexError);
                }
                let mask = (1 as $value) << bit;
                Ok(self.fetch_and(!mask, order) & mask != 0)
            }
        }
    };
}

integer_atomic!(AtomicU32, CoreAtomicU32, u32);
integer_atomic!(AtomicU64, CoreAtomicU64, u64);
integer_atomic!(AtomicUsize, CoreAtomicUsize, usize);

#[repr(transparent)]
pub struct AtomicPtr<T> {
    value: CoreAtomicPtr<T>,
}

impl<T> AtomicPtr<T> {
    pub const fn new(value: *mut T) -> Self {
        Self {
            value: CoreAtomicPtr::new(value),
        }
    }

    #[inline(always)]
    pub fn load(&self, order: LoadOrder) -> *mut T {
        self.value.load(order.as_core())
    }

    #[inline(always)]
    pub fn store(&self, value: *mut T, order: StoreOrder) {
        self.value.store(value, order.as_core());
    }

    #[inline(always)]
    pub fn exchange(&self, value: *mut T, order: RmwOrder) -> *mut T {
        self.value.swap(value, order.as_core())
    }

    #[inline(always)]
    pub fn compare_exchange(
        &self,
        current: *mut T,
        new: *mut T,
        order: CompareExchangeOrder,
    ) -> Result<*mut T, *mut T> {
        self.value.compare_exchange(
            current,
            new,
            order.success.as_core(),
            order.failure.as_core(),
        )
    }
}

#[inline(always)]
pub fn fence(order: FenceOrder) {
    core_fence(order.as_core());
}

#[inline(always)]
pub fn compiler_fence(order: FenceOrder) {
    core_compiler_fence(order.as_core());
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RefCountError {
    InitialValue,
    Overflow,
    Underflow,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RefRelease {
    pub remaining: u32,
    pub became_zero: bool,
}

pub struct RefCount {
    value: AtomicU32,
}

impl RefCount {
    pub const fn try_new(value: u32) -> Result<Self, RefCountError> {
        if value == 0 || value > MAX_REFCOUNT {
            Err(RefCountError::InitialValue)
        } else {
            Ok(Self {
                value: AtomicU32::new(value),
            })
        }
    }

    pub fn load(&self) -> u32 {
        self.value.load(LoadOrder::Acquire)
    }

    pub fn acquire(&self) -> Result<u32, RefCountError> {
        let mut observed = self.value.load(LoadOrder::Relaxed);
        loop {
            if observed == 0 {
                return Err(RefCountError::Underflow);
            }
            if observed == MAX_REFCOUNT {
                return Err(RefCountError::Overflow);
            }
            match self.value.compare_exchange_weak(
                observed,
                observed + 1,
                CompareExchangeOrder::RELAXED,
            ) {
                Ok(_) => return Ok(observed + 1),
                Err(current) => {
                    observed = current;
                    spin_loop();
                }
            }
        }
    }

    pub fn release(&self) -> Result<RefRelease, RefCountError> {
        let mut observed = self.value.load(LoadOrder::Relaxed);
        loop {
            if observed == 0 {
                return Err(RefCountError::Underflow);
            }
            let remaining = observed - 1;
            match self.value.compare_exchange_weak(
                observed,
                remaining,
                CompareExchangeOrder::ACQ_REL,
            ) {
                Ok(_) => {
                    return Ok(RefRelease {
                        remaining,
                        became_zero: remaining == 0,
                    });
                }
                Err(current) => {
                    observed = current;
                    spin_loop();
                }
            }
        }
    }
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_load_acquire(value: *const AtomicU64) -> u64 {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe { (*value).load(LoadOrder::Acquire) }
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_store_release(value: *const AtomicU64, next: u64) {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe { (*value).store(next, StoreOrder::Release) };
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_exchange_seqcst(
    value: *const AtomicU64,
    next: u64,
) -> u64 {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe { (*value).exchange(next, RmwOrder::SeqCst) }
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_compare_exchange_acqrel(
    value: *const AtomicU64,
    current: u64,
    next: u64,
) -> u64 {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe {
        (*value)
            .compare_exchange(current, next, CompareExchangeOrder::ACQ_REL)
            .unwrap_or_else(|observed| observed)
    }
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_fetch_add_relaxed(
    value: *const AtomicU64,
    increment: u64,
) -> u64 {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe { (*value).fetch_add(increment, RmwOrder::Relaxed) }
}

#[unsafe(no_mangle)]
#[inline(never)]
/// # Safety
///
/// `value` must point to a live, aligned `AtomicU64` for the complete call.
pub unsafe extern "C" fn poole_atomic_audit_fetch_or_acqrel(
    value: *const AtomicU64,
    mask: u64,
) -> u64 {
    // SAFETY: PKATOM1 callers pass a live, aligned AtomicU64 for the call duration.
    unsafe { (*value).fetch_or(mask, RmwOrder::AcqRel) }
}

#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn poole_atomic_audit_fence_seqcst() {
    fence(FenceOrder::SeqCst);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn order_matrix_rejects_every_invalid_combination() {
        assert_eq!(
            classify_order_matrix(),
            OrderMatrix {
                load_orders: 3,
                store_orders: 3,
                rmw_orders: 5,
                fence_orders: 4,
                compare_exchange_pairs: 9,
                rejected_combinations: 11,
            }
        );
        assert_eq!(
            CompareExchangeOrder::new(RmwOrder::Release, LoadOrder::Acquire),
            Err(OrderError::CompareExchangeFailureStrongerThanSuccess)
        );
    }

    #[test]
    fn integer_operations_cover_all_supported_families() {
        let value = AtomicU64::new(7);
        assert_eq!(value.load(LoadOrder::Relaxed), 7);
        value.store(9, StoreOrder::Release);
        assert_eq!(value.exchange(11, RmwOrder::AcqRel), 9);
        assert_eq!(
            value.compare_exchange(11, 13, CompareExchangeOrder::ACQ_REL),
            Ok(11)
        );
        assert_eq!(value.fetch_add(5, RmwOrder::Relaxed), 13);
        assert_eq!(value.fetch_sub(2, RmwOrder::Acquire), 18);
        assert_eq!(value.fetch_or(0x20, RmwOrder::Release), 16);
        assert_eq!(value.fetch_xor(0x10, RmwOrder::SeqCst), 48);
        assert_eq!(value.fetch_and(0x1f, RmwOrder::AcqRel), 32);
        assert_eq!(value.load(LoadOrder::SeqCst), 0);
    }

    #[test]
    fn bit_test_modification_is_bounded_by_type_width() {
        let value = AtomicU32::new(0);
        assert_eq!(value.fetch_set_bit(31, RmwOrder::AcqRel), Ok(false));
        assert_eq!(value.fetch_set_bit(31, RmwOrder::AcqRel), Ok(true));
        assert_eq!(value.fetch_clear_bit(31, RmwOrder::AcqRel), Ok(true));
        assert_eq!(
            value.fetch_set_bit(32, RmwOrder::AcqRel),
            Err(BitIndexError)
        );
    }

    #[test]
    fn pointer_exchange_and_compare_exchange_preserve_typed_identity() {
        let mut first = 3u64;
        let mut second = 5u64;
        let pointer = AtomicPtr::new(&mut first);
        assert_eq!(pointer.load(LoadOrder::Acquire), &mut first as *mut u64);
        assert_eq!(
            pointer.exchange(&mut second, RmwOrder::AcqRel),
            &mut first as *mut u64
        );
        assert_eq!(
            pointer.compare_exchange(&mut second, &mut first, CompareExchangeOrder::ACQ_REL,),
            Ok(&mut second as *mut u64)
        );
    }

    #[test]
    fn reference_count_rejects_zero_overflow_and_underflow() {
        assert!(matches!(
            RefCount::try_new(0),
            Err(RefCountError::InitialValue)
        ));
        let maximum = RefCount::try_new(MAX_REFCOUNT).unwrap();
        assert_eq!(maximum.acquire(), Err(RefCountError::Overflow));
        let count = RefCount::try_new(1).unwrap();
        assert_eq!(count.acquire(), Ok(2));
        assert_eq!(count.release().unwrap().remaining, 1);
        assert!(count.release().unwrap().became_zero);
        assert_eq!(count.release(), Err(RefCountError::Underflow));
    }

    #[test]
    fn fences_accept_only_typed_non_relaxed_orders() {
        compiler_fence(FenceOrder::Acquire);
        compiler_fence(FenceOrder::Release);
        fence(FenceOrder::AcqRel);
        fence(FenceOrder::SeqCst);
        assert_eq!(
            FenceOrder::try_from(MemoryOrder::Relaxed),
            Err(OrderError::InvalidFence)
        );
    }

    #[test]
    fn audit_entry_points_execute_the_frozen_operations() {
        let value = AtomicU64::new(1);
        // SAFETY: every call uses the live local atomic for the complete call.
        unsafe {
            poole_atomic_audit_store_release(&value, 2);
            assert_eq!(poole_atomic_audit_load_acquire(&value), 2);
            assert_eq!(poole_atomic_audit_exchange_seqcst(&value, 3), 2);
            assert_eq!(poole_atomic_audit_compare_exchange_acqrel(&value, 3, 4), 3);
            assert_eq!(poole_atomic_audit_fetch_add_relaxed(&value, 2), 4);
            assert_eq!(poole_atomic_audit_fetch_or_acqrel(&value, 8), 6);
        }
        poole_atomic_audit_fence_seqcst();
        assert_eq!(value.load(LoadOrder::Acquire), 14);
    }
}
