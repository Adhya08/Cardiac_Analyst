import sys
import os
import torch

def main():
    print("=" * 60)
    print(" CARDIAC ANALYST — KAGGLE GPU HELLO WORLD TEST")
    print("=" * 60)
    print(f"Python Version: {sys.version}")
    print(f"PyTorch Version: {torch.__version__}")
    
    cuda_available = torch.cuda.is_available()
    print(f"\nCUDA Available: {cuda_available}")
    
    if cuda_available:
        device_count = torch.cuda.device_count()
        device_name = torch.cuda.get_device_name(0)
        capability = torch.cuda.get_device_capability(0)
        total_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        
        print(f"GPU Count: {device_count}")
        print(f"GPU Model: {device_name}")
        print(f"Compute Capability: {capability}")
        print(f"Total VRAM: {total_memory_gb:.2f} GB")
        
        # Test tensor operation on GPU
        x = torch.randn(2048, 2048, device="cuda")
        y = torch.matmul(x, x)
        torch.cuda.synchronize()
        print("\nCUDA Matrix Multiplication Test (2048x2048): SUCCESS")
    else:
        print("\nWARNING: No CUDA device detected! Check kernel-metadata enable_gpu setting or phone verification status.")
        
    print("\n--- Checking Dataset Mounts (/kaggle/input) ---")
    if os.path.exists("/kaggle/input"):
        for root, dirs, files in os.walk("/kaggle/input"):
            print(f"Path: {root}")
            for d in dirs[:5]:
                print(f"  [DIR] {d}")
            for f in files[:5]:
                print(f"  [FILE] {f}")
            break
    else:
        print("No /kaggle/input found.")
        
    # Write output artifact
    status_str = "SUCCESS" if cuda_available else "FAILED"
    with open("gpu_check_result.txt", "w") as f:
        f.write(f"GPU: {torch.cuda.get_device_name(0) if cuda_available else 'None'}\n")
        f.write(f"CUDA: {cuda_available}\n")
        f.write(f"Status: {status_str}\n")
        
    if not cuda_available:
        print("\nTest FAILED: No CUDA device detected.")
        print("=" * 60)
        sys.exit(1)

    print("\nTest completed successfully. Output written to gpu_check_result.txt.")
    print("=" * 60)

if __name__ == "__main__":
    main()
