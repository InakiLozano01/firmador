import importlib
import sys
import unittest
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


def load_transaction_module():
    try:
        return importlib.import_module("signing_transaction")
    except ModuleNotFoundError as exc:
        raise AssertionError("signing_transaction Module has not been implemented") from exc


class FakeWorker:
    def __init__(self, signatures=None, sign_error=None):
        self.signatures = signatures or ["signature"]
        self.sign_error = sign_error
        self.sign_calls = []
        self.close_count = 0

    def sign(self, data_to_sign):
        self.sign_calls.append(data_to_sign)
        if self.sign_error:
            raise self.sign_error
        return self.signatures

    def close(self):
        self.close_count += 1


class FakeTimer:
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.callback()


class SigningTransactionManagerTests(unittest.TestCase):
    def test_consumes_transaction_after_one_batch_sign(self):
        module = load_transaction_module()
        worker = FakeWorker(["sig-a", "sig-b"])
        manager = module.SigningTransactionManager(ttl_seconds=300)
        token_id = manager.create(
            worker=worker,
            origin="https://dynamic.example",
            key_id="CERT-FINGERPRINT",
        )

        signatures = manager.consume(
            token_id=token_id,
            key_id="CERT-FINGERPRINT",
            origin="https://dynamic.example",
            data_to_sign=["a", "b"],
        )

        self.assertEqual(["sig-a", "sig-b"], signatures)
        self.assertEqual([["a", "b"]], worker.sign_calls)
        self.assertEqual(1, worker.close_count)
        with self.assertRaises(module.TransactionNotFoundError):
            manager.consume(
                token_id=token_id,
                key_id="CERT-FINGERPRINT",
                origin="https://dynamic.example",
                data_to_sign=["again"],
            )

    def test_rejects_different_origin_without_consuming_transaction(self):
        module = load_transaction_module()
        worker = FakeWorker()
        manager = module.SigningTransactionManager(ttl_seconds=300)
        token_id = manager.create(worker, "https://trusted.example", "KEY")

        with self.assertRaises(module.TransactionOriginMismatchError):
            manager.consume(token_id, "KEY", "https://evil.example", ["payload"])

        self.assertEqual([], worker.sign_calls)
        self.assertEqual(
            ["signature"],
            manager.consume(token_id, "KEY", "https://trusted.example", ["payload"]),
        )

    def test_rejects_key_mismatch_without_using_worker(self):
        module = load_transaction_module()
        worker = FakeWorker()
        manager = module.SigningTransactionManager(ttl_seconds=300)
        token_id = manager.create(worker, "https://trusted.example", "KEY-A")

        with self.assertRaises(module.TransactionKeyMismatchError):
            manager.consume(token_id, "KEY-B", "https://trusted.example", ["payload"])

        self.assertEqual([], worker.sign_calls)
        manager.discard(token_id)
        self.assertEqual(1, worker.close_count)

    def test_expired_transaction_is_closed_and_rejected(self):
        module = load_transaction_module()
        now = [100.0]
        worker = FakeWorker()
        manager = module.SigningTransactionManager(
            ttl_seconds=5,
            clock=lambda: now[0],
        )
        token_id = manager.create(worker, None, "KEY")
        now[0] = 106.0

        with self.assertRaises(module.TransactionExpiredError):
            manager.consume(token_id, "KEY", None, ["payload"])

        self.assertEqual([], worker.sign_calls)
        self.assertEqual(1, worker.close_count)

    def test_failed_sign_still_consumes_and_closes_transaction(self):
        module = load_transaction_module()
        worker = FakeWorker(sign_error=RuntimeError("driver failed"))
        manager = module.SigningTransactionManager(ttl_seconds=300)
        token_id = manager.create(worker, None, "KEY")

        with self.assertRaisesRegex(RuntimeError, "driver failed"):
            manager.consume(token_id, "KEY", None, ["payload"])

        self.assertEqual(1, worker.close_count)
        with self.assertRaises(module.TransactionNotFoundError):
            manager.consume(token_id, "KEY", None, ["payload"])

    def test_abandoned_transaction_closes_worker_at_timeout(self):
        module = load_transaction_module()
        timers = []

        def timer_factory(delay, callback):
            timer = FakeTimer(delay, callback)
            timers.append(timer)
            return timer

        worker = FakeWorker()
        manager = module.SigningTransactionManager(
            ttl_seconds=300,
            timer_factory=timer_factory,
        )
        token_id = manager.create(worker, None, "KEY")

        self.assertEqual(300, timers[0].delay)
        self.assertTrue(timers[0].started)
        timers[0].fire()

        self.assertEqual(1, worker.close_count)
        with self.assertRaises(module.TransactionNotFoundError):
            manager.consume(token_id, "KEY", None, ["payload"])

    def test_active_binding_matches_origin_and_single_transaction(self):
        module = load_transaction_module()
        worker = FakeWorker()
        manager = module.SigningTransactionManager(ttl_seconds=300)
        token_id = manager.create(worker, "https://tapir.example", "KEY")

        matched = manager.get_active_binding("https://tapir.example")
        mismatched = manager.get_active_binding("https://evil.example")
        single = manager.get_single_active_binding()

        self.assertEqual((token_id, "KEY", "https://tapir.example"), matched)
        self.assertIsNone(mismatched)
        self.assertEqual((token_id, "KEY", "https://tapir.example"), single)
        manager.discard(token_id)

    def test_rejects_second_active_transaction(self):
        module = load_transaction_module()
        first_worker = FakeWorker()
        second_worker = FakeWorker()
        manager = module.SigningTransactionManager(ttl_seconds=300)
        first_token = manager.create(first_worker, None, "KEY-1")

        with self.assertRaises(module.TransactionInProgressError):
            manager.create(second_worker, None, "KEY-2")

        self.assertEqual(0, second_worker.close_count)
        manager.discard(first_token)


if __name__ == "__main__":
    unittest.main()
