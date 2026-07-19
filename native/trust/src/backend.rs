use sha2::{Digest, Sha256};

use crate::{STATE_FLAG_AUTHENTICATED_BACKEND, STATE_FLAG_COMMITTED, State, parse_state};

pub const BACKEND_CONTRACT_ID: &str = "PBSTATE1";
pub const LOGICAL_DIGEST_DOMAIN: &[u8] = b"POOLEOS/PBTS1/LOGICAL/V1\0";
pub const REDUNDANT_COPY_MASK: u8 = 0b11;
pub const TRANSITION_STEP_COUNT: u8 = 9;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BackendError {
    AnchorAuthentication,
    AnchorMonotonicity,
    AnchorNumbers,
    Requirements,
    AnchorRollback,
    NoAuthenticatedCopy,
    PreviousState,
    AnchorDigest,
    FutureState,
    StateRollback,
    BackendWritable,
    RepairCapacity,
    GenerationOverflow,
    MigrationRollback,
}

impl BackendError {
    pub const fn code(self) -> &'static str {
        match self {
            Self::AnchorAuthentication => "pbtrust_backend_anchor_authentication",
            Self::AnchorMonotonicity => "pbtrust_backend_anchor_monotonicity",
            Self::AnchorNumbers => "pbtrust_backend_anchor_numbers",
            Self::Requirements => "pbtrust_backend_requirements",
            Self::AnchorRollback => "pbtrust_backend_anchor_rollback",
            Self::NoAuthenticatedCopy => "pbtrust_backend_no_authenticated_copy",
            Self::PreviousState => "pbtrust_backend_previous_state",
            Self::AnchorDigest => "pbtrust_backend_anchor_digest",
            Self::FutureState => "pbtrust_backend_future_state",
            Self::StateRollback => "pbtrust_backend_state_rollback",
            Self::BackendWritable => "pbtrust_backend_writable",
            Self::RepairCapacity => "pbtrust_backend_repair_capacity",
            Self::GenerationOverflow => "pbtrust_backend_generation_overflow",
            Self::MigrationRollback => "pbtrust_backend_migration_rollback",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MonotonicAnchor {
    pub authenticated: bool,
    pub monotonic: bool,
    pub state_generation: u64,
    pub store_epoch: u64,
    pub auth_profile: u16,
    pub logical_state_sha256: [u8; 32],
    pub previous_state_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BackendRequirements {
    pub minimum_state_generation: u64,
    pub minimum_store_epoch: u64,
    pub target_store_epoch: u64,
    pub target_auth_profile: u16,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BackendAccess {
    pub writable: bool,
    pub repair_capacity: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BackendCopy<'a> {
    pub bytes: Option<&'a [u8]>,
    pub authentication_verified: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BackendSelection {
    pub selected_copy: u8,
    pub present_copy_mask: u8,
    pub parsed_copy_mask: u8,
    pub authenticated_copy_mask: u8,
    pub anchored_copy_mask: u8,
    pub repair_copy_mask: u8,
    pub stale_copy_mask: u8,
    pub future_copy_mask: u8,
    pub state_generation: u64,
    pub store_epoch: u64,
    pub auth_profile: u16,
    pub logical_state_sha256: [u8; 32],
    pub previous_state_sha256: [u8; 32],
    pub target_store_epoch: u64,
    pub target_auth_profile: u16,
    pub migration_required: bool,
    pub authority_grants: u8,
    pub state_writes: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BackendTransitionPlan {
    pub source_copy: u8,
    pub target_copy: u8,
    pub next_generation: u64,
    pub target_store_epoch: u64,
    pub target_auth_profile: u16,
    pub previous_state_sha256: [u8; 32],
    pub ordered_step_count: u8,
    pub state_writes_performed: u8,
    pub anchor_writes_performed: u8,
    pub authority_grants: u8,
}

#[derive(Clone, Copy)]
struct Candidate<'a> {
    state: State<'a>,
    logical_sha256: [u8; 32],
}

fn all_zero(value: &[u8; 32]) -> bool {
    value.iter().all(|byte| *byte == 0)
}

pub fn logical_state_sha256(state: &State<'_>) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(LOGICAL_DIGEST_DOMAIN);
    hasher.update(crate::MAJOR_VERSION.to_le_bytes());
    hasher.update(crate::MINOR_VERSION.to_le_bytes());
    hasher.update((STATE_FLAG_COMMITTED | STATE_FLAG_AUTHENTICATED_BACKEND).to_le_bytes());
    hasher.update(state.auth_profile.to_le_bytes());
    hasher.update(state.state_generation.to_le_bytes());
    hasher.update(state.store_epoch.to_le_bytes());
    hasher.update(state.minimum_secure_version.to_le_bytes());
    hasher.update(state.accepted_manifest_version.to_le_bytes());
    hasher.update(state.accepted_policy_version.to_le_bytes());
    hasher.update(state.policy_sha256);
    hasher.update(state.manifest_sha256);
    hasher.update(state.kernel_sha256);
    hasher.update(state.retained_set_sha256);
    hasher.update(state.previous_state_sha256);
    let digest = hasher.finalize();
    let mut output = [0u8; 32];
    output.copy_from_slice(&digest);
    output
}

fn validate_anchor(
    anchor: &MonotonicAnchor,
    requirements: &BackendRequirements,
) -> Result<(), BackendError> {
    if !anchor.authenticated {
        return Err(BackendError::AnchorAuthentication);
    }
    if !anchor.monotonic {
        return Err(BackendError::AnchorMonotonicity);
    }
    if anchor.state_generation == 0
        || anchor.store_epoch == 0
        || anchor.auth_profile == 0
        || all_zero(&anchor.logical_state_sha256)
        || ((anchor.state_generation == 1) != all_zero(&anchor.previous_state_sha256))
    {
        return Err(BackendError::AnchorNumbers);
    }
    if requirements.minimum_state_generation == 0
        || requirements.minimum_store_epoch == 0
        || requirements.target_store_epoch == 0
        || requirements.target_auth_profile == 0
        || requirements.target_store_epoch < requirements.minimum_store_epoch
        || requirements.target_store_epoch < anchor.store_epoch
    {
        return Err(BackendError::Requirements);
    }
    if anchor.state_generation < requirements.minimum_state_generation
        || anchor.store_epoch < requirements.minimum_store_epoch
    {
        return Err(BackendError::AnchorRollback);
    }
    Ok(())
}

pub fn select_backend_state(
    copies: &[BackendCopy<'_>; 2],
    anchor: &MonotonicAnchor,
    requirements: &BackendRequirements,
    access: &BackendAccess,
) -> Result<BackendSelection, BackendError> {
    validate_anchor(anchor, requirements)?;

    let mut candidates: [Option<Candidate<'_>>; 2] = [None, None];
    let mut present_mask = 0u8;
    let mut parsed_mask = 0u8;
    let mut authenticated_mask = 0u8;
    let mut anchored_mask = 0u8;
    let mut stale_mask = 0u8;
    let mut future_mask = 0u8;
    let mut previous_mismatch_mask = 0u8;
    let mut digest_mismatch_mask = 0u8;

    for (index, copy) in copies.iter().enumerate() {
        let bit = 1u8 << index;
        let Some(bytes) = copy.bytes else {
            continue;
        };
        present_mask |= bit;
        let Ok(state) = parse_state(bytes) else {
            continue;
        };
        if state.copy_index != index as u8 {
            continue;
        }
        parsed_mask |= bit;
        if !copy.authentication_verified || state.flags & STATE_FLAG_AUTHENTICATED_BACKEND == 0 {
            continue;
        }
        authenticated_mask |= bit;
        let logical_sha256 = logical_state_sha256(&state);
        candidates[index] = Some(Candidate {
            state,
            logical_sha256,
        });

        if state.state_generation < anchor.state_generation
            || state.store_epoch < anchor.store_epoch
        {
            stale_mask |= bit;
            continue;
        }
        if state.state_generation > anchor.state_generation
            || state.store_epoch > anchor.store_epoch
        {
            future_mask |= bit;
            continue;
        }
        if state.previous_state_sha256 != anchor.previous_state_sha256 {
            previous_mismatch_mask |= bit;
            continue;
        }
        if state.auth_profile != anchor.auth_profile
            || logical_sha256 != anchor.logical_state_sha256
        {
            digest_mismatch_mask |= bit;
            continue;
        }
        anchored_mask |= bit;
    }

    if anchored_mask == 0 {
        if previous_mismatch_mask != 0 {
            return Err(BackendError::PreviousState);
        }
        if digest_mismatch_mask != 0 {
            return Err(BackendError::AnchorDigest);
        }
        if future_mask != 0 {
            return Err(BackendError::FutureState);
        }
        if stale_mask != 0 {
            return Err(BackendError::StateRollback);
        }
        return Err(BackendError::NoAuthenticatedCopy);
    }

    if !access.writable {
        return Err(BackendError::BackendWritable);
    }
    let repair_mask = REDUNDANT_COPY_MASK & !anchored_mask;
    if repair_mask != 0 && !access.repair_capacity {
        return Err(BackendError::RepairCapacity);
    }

    let selected_copy = if anchored_mask & 1 != 0 { 0 } else { 1 };
    let selected = candidates[selected_copy as usize].ok_or(BackendError::AnchorDigest)?;
    let migration_required = selected.state.store_epoch < requirements.target_store_epoch
        || selected.state.auth_profile != requirements.target_auth_profile;

    Ok(BackendSelection {
        selected_copy,
        present_copy_mask: present_mask,
        parsed_copy_mask: parsed_mask,
        authenticated_copy_mask: authenticated_mask,
        anchored_copy_mask: anchored_mask,
        repair_copy_mask: repair_mask,
        stale_copy_mask: stale_mask,
        future_copy_mask: future_mask,
        state_generation: selected.state.state_generation,
        store_epoch: selected.state.store_epoch,
        auth_profile: selected.state.auth_profile,
        logical_state_sha256: selected.logical_sha256,
        previous_state_sha256: selected.state.previous_state_sha256,
        target_store_epoch: requirements.target_store_epoch,
        target_auth_profile: requirements.target_auth_profile,
        migration_required,
        authority_grants: 0,
        state_writes: 0,
    })
}

pub fn plan_backend_transition(
    selection: &BackendSelection,
) -> Result<BackendTransitionPlan, BackendError> {
    let anchored_mask = selection.anchored_copy_mask;
    let expected_repair_mask = REDUNDANT_COPY_MASK & !anchored_mask;
    let expected_migration = selection.store_epoch < selection.target_store_epoch
        || selection.auth_profile != selection.target_auth_profile;
    if selection.selected_copy >= 2
        || anchored_mask == 0
        || anchored_mask & !REDUNDANT_COPY_MASK != 0
        || anchored_mask & (1u8 << selection.selected_copy) == 0
        || selection.repair_copy_mask != expected_repair_mask
        || selection.state_generation == 0
        || selection.store_epoch == 0
        || selection.auth_profile == 0
        || all_zero(&selection.logical_state_sha256)
        || ((selection.state_generation == 1) != all_zero(&selection.previous_state_sha256))
        || selection.migration_required != expected_migration
        || selection.authority_grants != 0
        || selection.state_writes != 0
    {
        return Err(BackendError::Requirements);
    }
    if selection.target_store_epoch < selection.store_epoch || selection.target_auth_profile == 0 {
        return Err(BackendError::MigrationRollback);
    }
    let next_generation = selection
        .state_generation
        .checked_add(1)
        .ok_or(BackendError::GenerationOverflow)?;
    let target_copy = if selection.anchored_copy_mask == 0b01 {
        1
    } else if selection.anchored_copy_mask == 0b10 {
        0
    } else {
        1 - selection.selected_copy
    };
    Ok(BackendTransitionPlan {
        source_copy: selection.selected_copy,
        target_copy,
        next_generation,
        target_store_epoch: selection.target_store_epoch,
        target_auth_profile: selection.target_auth_profile,
        previous_state_sha256: selection.logical_state_sha256,
        ordered_step_count: TRANSITION_STEP_COUNT,
        state_writes_performed: 0,
        anchor_writes_performed: 0,
        authority_grants: 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        COMMIT_COMPLETE, COPY_COUNT, MAJOR_VERSION, MINOR_VERSION, STATE_BODY_BYTES, STATE_BYTES,
        STATE_MAGIC, sha256,
    };

    const POLICY: [u8; 32] = [0x11; 32];
    const MANIFEST: [u8; 32] = [0x22; 32];
    const KERNEL: [u8; 32] = [0x33; 32];
    const RETAINED: [u8; 32] = [0x44; 32];

    fn state(
        copy_index: u8,
        generation: u64,
        epoch: u64,
        auth_profile: u16,
        previous: [u8; 32],
    ) -> [u8; STATE_BYTES] {
        let mut output = [0u8; STATE_BYTES];
        output[..8].copy_from_slice(&STATE_MAGIC);
        output[8..10].copy_from_slice(&MAJOR_VERSION.to_le_bytes());
        output[10..12].copy_from_slice(&MINOR_VERSION.to_le_bytes());
        output[12..14].copy_from_slice(&(STATE_BYTES as u16).to_le_bytes());
        let flags = STATE_FLAG_COMMITTED | STATE_FLAG_AUTHENTICATED_BACKEND;
        output[14..16].copy_from_slice(&flags.to_le_bytes());
        output[16] = copy_index;
        output[17] = COPY_COUNT;
        output[18..20].copy_from_slice(&COMMIT_COMPLETE.to_le_bytes());
        output[20..22].copy_from_slice(&auth_profile.to_le_bytes());
        output[24..32].copy_from_slice(&generation.to_le_bytes());
        output[32..40].copy_from_slice(&epoch.to_le_bytes());
        output[40..48].copy_from_slice(&1u64.to_le_bytes());
        output[48..56].copy_from_slice(&1u64.to_le_bytes());
        output[56..64].copy_from_slice(&1u64.to_le_bytes());
        output[64..96].copy_from_slice(&POLICY);
        output[96..128].copy_from_slice(&MANIFEST);
        output[128..160].copy_from_slice(&KERNEL);
        output[160..192].copy_from_slice(&RETAINED);
        output[192..224].copy_from_slice(&previous);
        let digest = sha256(&output[..STATE_BODY_BYTES]);
        output[224..256].copy_from_slice(&digest);
        output
    }

    fn anchor_for(data: &[u8]) -> MonotonicAnchor {
        let parsed = parse_state(data).unwrap();
        MonotonicAnchor {
            authenticated: true,
            monotonic: true,
            state_generation: parsed.state_generation,
            store_epoch: parsed.store_epoch,
            auth_profile: parsed.auth_profile,
            logical_state_sha256: logical_state_sha256(&parsed),
            previous_state_sha256: parsed.previous_state_sha256,
        }
    }

    fn requirements() -> BackendRequirements {
        BackendRequirements {
            minimum_state_generation: 1,
            minimum_store_epoch: 1,
            target_store_epoch: 1,
            target_auth_profile: 1,
        }
    }

    fn access() -> BackendAccess {
        BackendAccess {
            writable: true,
            repair_capacity: true,
        }
    }

    #[test]
    fn logical_digest_excludes_only_redundant_copy_identity() {
        let copy0 = state(0, 1, 1, 1, [0u8; 32]);
        let copy1 = state(1, 1, 1, 1, [0u8; 32]);
        assert_ne!(sha256(&copy0), sha256(&copy1));
        assert_eq!(
            logical_state_sha256(&parse_state(&copy0).unwrap()),
            logical_state_sha256(&parse_state(&copy1).unwrap())
        );
    }

    #[test]
    fn healthy_copies_select_low_index_without_repair() {
        let copy0 = state(0, 1, 1, 1, [0u8; 32]);
        let copy1 = state(1, 1, 1, 1, [0u8; 32]);
        let selection = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&copy0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: Some(&copy1),
                    authentication_verified: true,
                },
            ],
            &anchor_for(&copy0),
            &requirements(),
            &access(),
        )
        .unwrap();
        assert_eq!(selection.selected_copy, 0);
        assert_eq!(selection.anchored_copy_mask, REDUNDANT_COPY_MASK);
        assert_eq!(selection.repair_copy_mask, 0);
        assert_eq!(selection.authority_grants, 0);
        assert_eq!(selection.state_writes, 0);
    }

    #[test]
    fn missing_copy_produces_plan_without_writing() {
        let copy0 = state(0, 1, 1, 1, [0u8; 32]);
        let selection = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&copy0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: None,
                    authentication_verified: false,
                },
            ],
            &anchor_for(&copy0),
            &requirements(),
            &access(),
        )
        .unwrap();
        assert_eq!(selection.repair_copy_mask, 0b10);
        let plan = plan_backend_transition(&selection).unwrap();
        assert_eq!(plan.target_copy, 1);
        assert_eq!(plan.next_generation, 2);
        assert_eq!(plan.ordered_step_count, TRANSITION_STEP_COUNT);
        assert_eq!(plan.state_writes_performed, 0);
    }

    #[test]
    fn future_copy_before_anchor_commit_is_not_selected() {
        let old0 = state(0, 1, 1, 1, [0u8; 32]);
        let old_digest = logical_state_sha256(&parse_state(&old0).unwrap());
        let future1 = state(1, 2, 1, 1, old_digest);
        let selection = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&old0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: Some(&future1),
                    authentication_verified: true,
                },
            ],
            &anchor_for(&old0),
            &requirements(),
            &access(),
        )
        .unwrap();
        assert_eq!(selection.selected_copy, 0);
        assert_eq!(selection.future_copy_mask, 0b10);
        assert_eq!(selection.repair_copy_mask, 0b10);
    }

    #[test]
    fn advanced_anchor_selects_new_copy_and_repairs_old() {
        let old0 = state(0, 1, 1, 1, [0u8; 32]);
        let old_digest = logical_state_sha256(&parse_state(&old0).unwrap());
        let new1 = state(1, 2, 1, 1, old_digest);
        let selection = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&old0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: Some(&new1),
                    authentication_verified: true,
                },
            ],
            &anchor_for(&new1),
            &requirements(),
            &access(),
        )
        .unwrap();
        assert_eq!(selection.selected_copy, 1);
        assert_eq!(selection.stale_copy_mask, 0b01);
        assert_eq!(selection.repair_copy_mask, 0b01);
    }

    #[test]
    fn unauthenticated_and_rollback_only_sets_fail_closed() {
        let copy0 = state(0, 1, 1, 1, [0u8; 32]);
        let copy1 = state(1, 1, 1, 1, [0u8; 32]);
        assert_eq!(
            select_backend_state(
                &[
                    BackendCopy {
                        bytes: Some(&copy0),
                        authentication_verified: false
                    },
                    BackendCopy {
                        bytes: Some(&copy1),
                        authentication_verified: false
                    },
                ],
                &anchor_for(&copy0),
                &requirements(),
                &access(),
            ),
            Err(BackendError::NoAuthenticatedCopy)
        );
        let future0 = state(0, 2, 1, 1, [0x55; 32]);
        let anchor = anchor_for(&future0);
        assert_eq!(
            select_backend_state(
                &[
                    BackendCopy {
                        bytes: Some(&copy0),
                        authentication_verified: true
                    },
                    BackendCopy {
                        bytes: Some(&copy1),
                        authentication_verified: true
                    },
                ],
                &anchor,
                &requirements(),
                &access(),
            ),
            Err(BackendError::StateRollback)
        );
    }

    #[test]
    fn repair_requires_writable_capacity() {
        let copy0 = state(0, 1, 1, 1, [0u8; 32]);
        let copies = [
            BackendCopy {
                bytes: Some(&copy0),
                authentication_verified: true,
            },
            BackendCopy {
                bytes: None,
                authentication_verified: false,
            },
        ];
        assert_eq!(
            select_backend_state(
                &copies,
                &anchor_for(&copy0),
                &requirements(),
                &BackendAccess {
                    writable: false,
                    repair_capacity: true
                },
            ),
            Err(BackendError::BackendWritable)
        );
        assert_eq!(
            select_backend_state(
                &copies,
                &anchor_for(&copy0),
                &requirements(),
                &BackendAccess {
                    writable: true,
                    repair_capacity: false
                },
            ),
            Err(BackendError::RepairCapacity)
        );
    }

    #[test]
    fn migration_and_generation_overflow_are_explicit() {
        let normal0 = state(0, 1, 1, 1, [0u8; 32]);
        let normal1 = state(1, 1, 1, 1, [0u8; 32]);
        let migration_requirements = BackendRequirements {
            target_store_epoch: 2,
            target_auth_profile: 2,
            ..requirements()
        };
        let migration = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&normal0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: Some(&normal1),
                    authentication_verified: true,
                },
            ],
            &anchor_for(&normal0),
            &migration_requirements,
            &access(),
        )
        .unwrap();
        assert!(migration.migration_required);
        let migration_plan = plan_backend_transition(&migration).unwrap();
        assert_eq!(migration_plan.target_copy, 1);
        assert_eq!(migration_plan.next_generation, 2);
        assert_eq!(migration_plan.target_store_epoch, 2);
        assert_eq!(migration_plan.target_auth_profile, 2);
        assert_eq!(migration_plan.state_writes_performed, 0);
        assert_eq!(migration_plan.anchor_writes_performed, 0);
        assert_eq!(migration_plan.authority_grants, 0);

        let malformed_selection = BackendSelection {
            selected_copy: 2,
            ..migration
        };
        assert_eq!(
            plan_backend_transition(&malformed_selection),
            Err(BackendError::Requirements)
        );

        let rollback_selection = BackendSelection {
            target_store_epoch: 0,
            ..migration
        };
        assert_eq!(
            plan_backend_transition(&rollback_selection),
            Err(BackendError::MigrationRollback)
        );

        let copy0 = state(0, u64::MAX, 1, 1, [0x55; 32]);
        let copy1 = state(1, u64::MAX, 1, 1, [0x55; 32]);
        let requirements = migration_requirements;
        let selection = select_backend_state(
            &[
                BackendCopy {
                    bytes: Some(&copy0),
                    authentication_verified: true,
                },
                BackendCopy {
                    bytes: Some(&copy1),
                    authentication_verified: true,
                },
            ],
            &anchor_for(&copy0),
            &requirements,
            &access(),
        )
        .unwrap();
        assert!(selection.migration_required);
        assert_eq!(
            plan_backend_transition(&selection),
            Err(BackendError::GenerationOverflow)
        );
    }
}
