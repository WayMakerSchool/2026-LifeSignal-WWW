"""학습 윈도우 어그멘테이션 회귀 테스트."""

from __future__ import annotations

import unittest

import numpy as np

from AI.augmentation import augment_training_windows


class TrainingAugmentationTest(unittest.TestCase):
    def test_is_disabled_when_copy_count_is_zero(self) -> None:
        samples = np.ones((2, 5, 2), dtype=np.float32)
        labels = np.asarray(["empty", "human"])
        result_samples, result_labels = augment_training_windows(
            samples,
            labels,
            ("target_energy", "status"),
        )
        np.testing.assert_array_equal(result_samples, samples)
        np.testing.assert_array_equal(result_labels, labels)

    def test_augments_numeric_signal_but_preserves_status(self) -> None:
        samples = np.asarray(
            [
                [[50.0, 0.0], [70.0, 0.0], [90.0, 0.0]],
                [[500.0, 1.0], [550.0, 1.0], [600.0, 1.0]],
            ],
            dtype=np.float32,
        )
        labels = np.asarray(["empty", "human"])
        augmented, augmented_labels = augment_training_windows(
            samples,
            labels,
            ("target_energy", "status"),
            copies=2,
            jitter=0.05,
            scale=0.05,
            random_state=7,
        )

        self.assertEqual(augmented.shape, (6, 3, 2))
        self.assertEqual(augmented_labels.tolist(), labels.tolist() * 3)
        np.testing.assert_array_equal(augmented[:2], samples)
        np.testing.assert_array_equal(
            augmented[:, :, 1],
            np.concatenate([samples[:, :, 1]] * 3),
        )
        self.assertTrue(np.all(augmented[:, :, 0] >= 0.0))
        self.assertFalse(np.array_equal(augmented[2:4, :, 0], samples[:, :, 0]))


if __name__ == "__main__":
    unittest.main()
