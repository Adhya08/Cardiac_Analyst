"""
Conversion and Benchmarking: Keras -> ONNX & TFLite
===================================================
1. Loads best_model.keras from Phase 4 training output.
2. Converts to TFLite (float32).
3. Converts to ONNX (opset 13).
4. Verifies output parity (max absolute tolerance < 1e-4) across test samples.
5. Measures exact file sizes and inference latencies.
6. Exports conversion_benchmark.json, model.onnx, and model.tflite.
"""

import os
import sys
import time
import json
import subprocess
import numpy as np

# Install tf2onnx and onnxruntime
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "tf2onnx", "onnx", "onnxruntime"])

import tensorflow as tf
import tf2onnx
import onnxruntime as ort

print(f"[Setup] TensorFlow Version: {tf.__version__}")
print(f"[Setup] ONNX Runtime Version: {ort.__version__}")

# Find best_model.keras
keras_path = None
for root, _, files in os.walk("/kaggle/input"):
    if "best_model.keras" in files:
        keras_path = os.path.join(root, "best_model.keras")
        break

if not keras_path or not os.path.exists(keras_path):
    raise FileNotFoundError(f"Could not locate best_model.keras under /kaggle/input")

print(f"[Input] Found Keras model at: {keras_path}")
keras_size_bytes = os.path.getsize(keras_path)
keras_size_mb = keras_size_bytes / (1024 * 1024)

# 1. Load Keras model
t0 = time.time()
keras_model = tf.keras.models.load_model(keras_path, compile=False)
t_keras_load = time.time() - t0
print(f"[Keras] Loaded in {t_keras_load:.2f}s. Size: {keras_size_mb:.2f} MB")

# 2. Convert to TFLite
output_dir = "/kaggle/working"
tflite_path = os.path.join(output_dir, "model.tflite")
print("[TFLite] Converting Keras model to TFLite...")
converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
tflite_bytes = converter.convert()
with open(tflite_path, "wb") as f:
    f.write(tflite_bytes)
tflite_size_bytes = os.path.getsize(tflite_path)
tflite_size_mb = tflite_size_bytes / (1024 * 1024)
print(f"[TFLite] Saved to {tflite_path}. Size: {tflite_size_mb:.2f} MB")

# 3. Convert to ONNX
onnx_path = os.path.join(output_dir, "model.onnx")
print("[ONNX] Converting Keras model to ONNX...")
spec = (tf.TensorSpec((None, 1000, 12), tf.float32, name="ecg_12lead_input"),)
model_proto, _ = tf2onnx.convert.from_keras(
    keras_model,
    input_signature=spec,
    opset=13,
    output_path=onnx_path
)
onnx_size_bytes = os.path.getsize(onnx_path)
onnx_size_mb = onnx_size_bytes / (1024 * 1024)
print(f"[ONNX] Saved to {onnx_path}. Size: {onnx_size_mb:.2f} MB")

# 4. Parity and Latency Benchmarking
print("\n[Benchmarking] Preparing test samples for output parity and latency tests...")
np.random.seed(42)
test_batch = np.random.randn(100, 1000, 12).astype(np.float32)

# Warmup and test Keras
keras_preds = keras_model.predict(test_batch, batch_size=1, verbose=0)
t0 = time.time()
for i in range(100):
    _ = keras_model(test_batch[i:i+1], training=False)
keras_latency_ms = ((time.time() - t0) / 100.0) * 1000.0

# Test TFLite
interpreter = tf.lite.Interpreter(model_path=tflite_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

tflite_preds = []
t0 = time.time()
for i in range(100):
    interpreter.set_tensor(input_details[0]['index'], test_batch[i:i+1])
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details[0]['index'])
    tflite_preds.append(output_data[0])
tflite_latency_ms = ((time.time() - t0) / 100.0) * 1000.0
tflite_preds = np.array(tflite_preds)

# Test ONNX Runtime
session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
input_name = session.get_inputs()[0].name
onnx_preds = []
t0 = time.time()
for i in range(100):
    out = session.run(None, {input_name: test_batch[i:i+1]})[0]
    onnx_preds.append(out[0])
onnx_latency_ms = ((time.time() - t0) / 100.0) * 1000.0
onnx_preds = np.array(onnx_preds)

# Calculate Parity
onnx_diff = np.max(np.abs(keras_preds - onnx_preds))
tflite_diff = np.max(np.abs(keras_preds - tflite_preds))

onnx_speedup = round(keras_latency_ms / onnx_latency_ms, 2)
onnx_reduction = round((1.0 - onnx_size_mb / keras_size_mb) * 100, 1)
parity_met = bool(onnx_diff < 1e-4)
parity_str = f"numerical parity verified (max diff {onnx_diff:.1e} < 1e-4)" if parity_met else f"numerical parity FAILED (max diff {onnx_diff:.1e} >= 1e-4)"
recommendation_text = (
    f"Use ONNX Runtime (.onnx): {onnx_reduction}% size reduction ({keras_size_mb:.1f}MB to {onnx_size_mb:.1f}MB), "
    f"{onnx_speedup}x faster CPU inference, and {parity_str}."
)

benchmark_results = {
    "frameworks": {
        "keras": {
            "format": ".keras (HDF5/zip)",
            "size_mb": round(keras_size_mb, 2),
            "latency_ms_per_sample": round(keras_latency_ms, 2),
            "max_abs_diff_from_keras": 0.0,
            "status": "baseline"
        },
        "onnx": {
            "format": ".onnx (Open Neural Network Exchange)",
            "size_mb": round(onnx_size_mb, 2),
            "latency_ms_per_sample": round(onnx_latency_ms, 2),
            "max_abs_diff_from_keras": float(onnx_diff),
            "speedup_vs_keras": onnx_speedup,
            "size_reduction_percent": onnx_reduction,
            "parity_verified": parity_met
        },
        "tflite": {
            "format": ".tflite (FlatBuffer)",
            "size_mb": round(tflite_size_mb, 2),
            "latency_ms_per_sample": round(tflite_latency_ms, 2),
            "max_abs_diff_from_keras": float(tflite_diff),
            "speedup_vs_keras": round(keras_latency_ms / tflite_latency_ms, 2),
            "size_reduction_percent": round((1.0 - tflite_size_mb / keras_size_mb) * 100, 1),
            "parity_verified": bool(tflite_diff < 1e-4)
        }
    },
    "tolerance_threshold": 1e-4,
    "recommendation": recommendation_text
}

with open(os.path.join(output_dir, "conversion_benchmark.json"), "w") as f:
    json.dump(benchmark_results, f, indent=2)

print("\n" + "=" * 70)
print("             FORMAT CONVERSION & RUNTIME BENCHMARK")
print("=" * 70)
print(f"Keras (.keras)   : Size = {keras_size_mb:6.2f} MB | Latency = {keras_latency_ms:6.2f} ms/sample")
print(f"ONNX (.onnx)     : Size = {onnx_size_mb:6.2f} MB | Latency = {onnx_latency_ms:6.2f} ms/sample | Max Diff = {onnx_diff:.2e}")
print(f"TFLite (.tflite) : Size = {tflite_size_mb:6.2f} MB | Latency = {tflite_latency_ms:6.2f} ms/sample | Max Diff = {tflite_diff:.2e}")
print("=" * 70)
print("[Done] Conversion and verification complete!")
