"""Small independent checks of the interpreter and runner's failure boundaries."""
from pathlib import Path
import tempfile
import unittest

from firmware_emulator.cpu import CPU, signed
from firmware_emulator import load_images
from protocol import Link


class HarnessTests(unittest.TestCase):
    def cpu(self, *instructions):
        return CPU(b''.join(word.to_bytes(2, 'big') for word in instructions))

    def test_signed_values_keep_the_correct_width(self):
        self.assertEqual(signed(0xFF, 8), -1)
        self.assertEqual(signed(0x7FFF, 16), 32767)
        self.assertEqual(signed(0x80000000, 32), -2147483648)

    def test_register_values_wrap_to_32_bits(self):
        cpu = self.cpu(0xE0FF, 0x7002, 0x000B, 0x0009)
        self.assertEqual(cpu.call(0x08000000), 1)

    def test_branch_delay_slot_executes_before_destination(self):
        cpu = self.cpu(0xA000, 0xE007, 0x000B, 0x0009)
        self.assertEqual(cpu.call(0x08000000), 7)

    def test_memory_is_big_endian(self):
        cpu = self.cpu()
        cpu.write(0x09000000, 0x12345678, 4)
        self.assertEqual(cpu.read(0x09000000, 2), 0x1234)
        self.assertEqual(cpu.read(0x09000003, 1), 0x78)

    def test_unmapped_reads_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'unmapped read'):
            self.cpu().read(0x12345678, 1)

    def test_rom_writes_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'unmapped write'):
            self.cpu(0x0009).write(0x08000000, 0, 2)

    def test_unknown_instruction_is_not_silently_ignored(self):
        with self.assertRaisesRegex(RuntimeError, 'opcode ffff'):
            self.cpu(0xFFFF).call(0x08000000)

    def test_infinite_firmware_loop_has_an_instruction_limit(self):
        with self.assertRaisesRegex(RuntimeError, 'Instruction limit'):
            self.cpu(0xAFFE, 0x0009).call(0x08000000, limit=4)

    def test_unknown_firmware_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'DDI_SST_39VF400_00-07FFFF.bin'
            path.write_bytes(b'wrong dump')
            with self.assertRaisesRegex(ValueError, 'unsupported SHA-256'):
                load_images(directory)

    def test_game_driver_rejects_oversized_request_payload(self):
        with self.assertRaisesRegex(ValueError, 'protocol limit'):
            Link().request(0x15, bytes(256))
