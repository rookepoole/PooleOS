import copy
import unittest

from runtime import native_kernel_smp_mailbox as mailbox


def fixture(apic_id=1):
    """Literal protocol fixture, not emulator evidence or a readiness receipt."""
    start = (0x1000, 0x23000, 0x45000)[apic_id - 1]
    context = [0x0C000000, 0x07000200, 10, 25, 40]
    baseline = [0x504B534D50324D42, 2, 3, 1, apic_id, 0, apic_id, 0x0C000000,
                0x07000200, 0x80010023, start + 0x1000, 0x40620, 0xD00, 20, 30]
    runtime = [mailbox.checksum(baseline), 0x504B525450324355, 1, 5,
               start + 0xF000, start + 0x12000, start + 0xF040, start + 0xA000,
               start + 0x15000, start + 0x17000, start + 0x19000, start + 0x1B000,
               start + 0x1D000, 4096, 0x50580000 | apic_id, start + 0xF000,
               start + 0x12000, start + 0xA000, 3, 0, 2, 39, 4095, 24, 8, 16,
               27, 19, 0, 0x37F, 0x1F80, 0, 1, 1, 0, 3, 576, 576]
    return [context, baseline, runtime]


def encode(words):
    return ",".join(f"0x{word:016X}" for word in words)


def validate(words, apic_id=1):
    return mailbox.validate(*(encode(row) for row in words), mailbox.checksum(words[1]),
                            mailbox.checksum(words[2]), apic_id, (0x1000, 0x23000, 0x45000)[apic_id - 1])


def reseal(words):
    words[2][0] = mailbox.checksum(words[1])
    return words


class NativeKernelSmpMailboxTests(unittest.TestCase):
    def test_frozen_literal_wire_vector(self):
        words = fixture()
        self.assertEqual(0x55E6550945AA7543, mailbox.checksum(words[1]))
        self.assertEqual(0x01B5E3A608866465, mailbox.checksum(words[2]))
        self.assertEqual((5, 15, 38), tuple(map(len, words)))
        observation = validate(words)
        self.assertEqual(0x2000, observation["baseline"]["cr3"])
        self.assertEqual(0x10040, observation["runtime"]["expected_tss_base"])

    def test_all_three_private_snapshots(self):
        for apic_id in (1, 2, 3):
            with self.subTest(apic_id=apic_id):
                self.assertEqual(apic_id, validate(fixture(apic_id), apic_id)["baseline"]["observed_apic_id"])

    def test_every_semantic_word_rejects_coherent_invalid_values(self):
        count = 0
        for section, row in enumerate(fixture()):
            for index in range(len(row)):
                changed = fixture()
                changed[section][index] = 0 if changed[section][index] else 1
                if section == 2 and index == 19:
                    changed[section][index] = 4
                if section == 2 and index == 20:
                    changed[section][index] = 0x202
                if section != 2 or index != 0:
                    reseal(changed)
                with self.subTest(section=section, index=index), self.assertRaises(mailbox.MailboxEvidenceError):
                    validate(changed)
                count += 1
        self.assertEqual(58, count)

    def test_every_checksum_input_is_covered_without_resealing(self):
        words = fixture()
        for section in (1, 2):
            for index in range(len(words[section])):
                changed = copy.deepcopy(words)
                changed[section][index] ^= 1
                with self.subTest(section=section, index=index), self.assertRaises(mailbox.MailboxEvidenceError):
                    mailbox.validate(*(encode(row) for row in changed), mailbox.checksum(words[1]),
                                     mailbox.checksum(words[2]), 1, 0x1000)

    def test_digest_rebinding_and_types_rejected(self):
        words = fixture()
        for field in (0, 1):
            for value in (None, True, "0", -1, 1 << 64, 0, 1.0):
                checksums = [mailbox.checksum(words[1]), mailbox.checksum(words[2])]
                checksums[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(mailbox.MailboxEvidenceError):
                    mailbox.validate(*(encode(row) for row in words), *checksums, 1, 0x1000)

    def test_exact_shape_width_and_spelling(self):
        words = fixture()
        for section, fields, narrow in ((0, mailbox.CONTEXT_FIELDS, frozenset(mailbox.CONTEXT_FIELDS[:2])),
                                       (1, mailbox.BASELINE_FIELDS, mailbox.BASELINE_U32),
                                       (2, mailbox.RUNTIME_FIELDS, mailbox.RUNTIME_U32)):
            text = encode(words[section])
            cases = (None, [], text + ",0x0000000000000000", text.split(",", 1)[1],
                     text + " ", text.replace("0x", "0X", 1), text.replace("0x", "0x0", 1),
                     text.replace("0x", "", 1), text + "\n", text.replace(",", ",,", 1))
            for candidate in cases:
                with self.subTest(section=section, candidate=candidate), self.assertRaises(mailbox.MailboxEvidenceError):
                    mailbox.parse_words(candidate, fields, narrow)
            for index, field in enumerate(fields):
                if field in narrow:
                    changed = copy.deepcopy(words)
                    changed[section][index] |= 1 << 32
                    reseal(changed)
                    with self.subTest(section=section, field=field), self.assertRaises(mailbox.MailboxEvidenceError):
                        validate(changed)

    def test_reordered_identity_and_cross_ap_snapshot_rejected(self):
        for section, pair in ((0, (2, 4)), (1, (0, 1)), (1, (4, 5)), (2, (4, 5)), (2, (6, 7))):
            changed = fixture()
            left, right = pair
            changed[section][left], changed[section][right] = changed[section][right], changed[section][left]
            with self.subTest(section=section, pair=pair), self.assertRaises(mailbox.MailboxEvidenceError):
                validate(reseal(changed))
        for apic_id in (2, 3):
            with self.assertRaises(mailbox.MailboxEvidenceError):
                validate(fixture(apic_id))

    def test_timing_bounds_including_stop_after_online_window(self):
        validate(fixture())  # Stop is later than the all-online bound, before quiescence.
        for section, index, value in ((0, 2, 21), (0, 3, 19), (0, 4, 29),
                                      (1, 13, 26), (1, 14, 19), (1, 14, 41)):
            changed = fixture()
            changed[section][index] = value
            with self.subTest(section=section, index=index, value=value), self.assertRaises(mailbox.MailboxEvidenceError):
                validate(reseal(changed))

    def test_normalization_preserves_every_non_timing_word(self):
        observed = validate(fixture())
        for section, dynamic in (("context", mailbox.CONTEXT_FIELDS[2:]),
                                 ("baseline", ("tsc_online", "tsc_stop")),
                                 ("runtime", ("baseline_checksum",))):
            words = mailbox.normalized_words(observed[section], dynamic).split(",")
            for (name, value), encoded in zip(observed[section].items(), words, strict=True):
                self.assertEqual("<validated-dynamic>" if name in dynamic else f"0x{value:016X}", encoded)

    def test_checksum_unsigned_types_and_byte_order(self):
        self.assertEqual(0xA8C7F832281A39C5, mailbox.checksum([0]))
        self.assertNotEqual(mailbox.checksum([1]), mailbox.checksum([1 << 56]))
        for word in (True, None, -1, 1 << 64, 1.0, "1"):
            with self.subTest(word=word), self.assertRaises(mailbox.MailboxEvidenceError):
                mailbox.checksum([word])


if __name__ == "__main__":
    unittest.main()
