import os
import numpy as np
import matplotlib.pyplot as plt

os.makedirs('/workspace/public/demo_ecgs', exist_ok=True)

def generate_ecg(condition, filename, duration=10, fs=500):
    t = np.linspace(0, duration, int(duration * fs))
    
    # Base configuration
    hr = 70
    noise_amp = 0.05
    st_elev = 0
    t_inv = False
    irregular = False
    p_wave = True
    qrs_width = 0.08
    
    if condition == 'Normal':
        hr = 75
    elif condition == 'STEMI':
        st_elev = 0.5
        hr = 85
    elif condition == 'AFib':
        p_wave = False
        irregular = True
        hr = 110
        noise_amp = 0.15 # f-waves
    elif condition == 'VTach':
        hr = 160
        qrs_width = 0.16
        p_wave = False
    elif condition == 'Bradycardia':
        hr = 45
    elif condition == 'LBBB':
        qrs_width = 0.14
        hr = 70

    signal = np.zeros_like(t)
    
    # generate beats
    current_time = 0.5
    while current_time < duration - 1:
        # P wave
        if p_wave:
            p_t = (t >= current_time - 0.15) & (t < current_time - 0.05)
            signal[p_t] += 0.15 * np.sin(np.pi * (t[p_t] - (current_time - 0.15)) / 0.1)
            
        # QRS complex
        if not (condition == 'VTach'):
            # Q wave
            q_t = (t >= current_time - 0.02) & (t < current_time)
            signal[q_t] -= 0.2 * np.sin(np.pi * (t[q_t] - (current_time - 0.02)) / 0.02)
            
            # R wave
            r_t = (t >= current_time) & (t < current_time + qrs_width/2)
            signal[r_t] += 1.5 * np.sin(np.pi * (t[r_t] - current_time) / (qrs_width/2))
            
            # S wave
            if condition == 'LBBB':
                s_t = (t >= current_time + qrs_width/2) & (t < current_time + qrs_width)
                signal[s_t] -= 0.5 * np.sin(np.pi * (t[s_t] - (current_time + qrs_width/2)) / (qrs_width/2))
            else:
                s_t = (t >= current_time + qrs_width/2) & (t < current_time + qrs_width)
                signal[s_t] -= 0.3 * np.sin(np.pi * (t[s_t] - (current_time + qrs_width/2)) / (qrs_width/2))
        else:
            # Wide VTach complex
            v_t = (t >= current_time - qrs_width/2) & (t < current_time + qrs_width/2)
            signal[v_t] += 1.2 * np.sin(np.pi * (t[v_t] - (current_time - qrs_width/2)) / qrs_width)
            signal[v_t] += 0.5 * np.sin(2 * np.pi * (t[v_t] - (current_time - qrs_width/2)) / qrs_width)
            
        # ST segment & T wave
        if condition != 'VTach':
            st_t = (t >= current_time + qrs_width) & (t < current_time + qrs_width + 0.1)
            signal[st_t] += st_elev
            
            t_t = (t >= current_time + qrs_width + 0.1) & (t < current_time + qrs_width + 0.3)
            t_amp = -0.3 if t_inv else 0.4
            signal[t_t] += t_amp * np.sin(np.pi * (t[t_t] - (current_time + qrs_width + 0.1)) / 0.2) + st_elev * np.linspace(1, 0, len(t[t_t]))

        # advance time
        if irregular:
            current_time += (60 / hr) + np.random.uniform(-0.2, 0.2)
        else:
            current_time += 60 / hr

    # Add noise/baseline wander
    noise = np.random.normal(0, noise_amp, len(t))
    baseline = 0.5 * np.sin(2 * np.pi * 0.1 * t)
    signal += noise + baseline
    
    # Plot 12-lead like grid
    fig, axes = plt.subplots(4, 1, figsize=(12, 6), sharex=True, gridspec_kw={'hspace': 0.5})
    leads = [['I', 'aVR', 'V1', 'V4'], ['II', 'aVL', 'V2', 'V5'], ['III', 'aVF', 'V3', 'V6'], ['II (Rhythm)', '', '', '']]
    
    for i, ax in enumerate(axes):
        ax.plot(t, signal + np.random.normal(0, 0.05, len(t)), color='black', linewidth=1)
        ax.set_ylim(-2, 3)
        ax.grid(True, which='both', color='pink', alpha=0.5, linestyle='-')
        ax.minorticks_on()
        ax.grid(True, which='minor', color='pink', alpha=0.2, linestyle='-')
        ax.set_xticks(np.arange(0, 10, 0.2), minor=True)
        ax.set_yticks(np.arange(-2, 3, 0.5), minor=True)
        ax.set_ylabel(leads[i][0])
        ax.set_xlim(0, 10)
        
    plt.suptitle(f"12-Lead ECG - {condition} Pattern", y=0.95, fontsize=14)
    plt.tight_path = True
    plt.savefig(f'/workspace/public/demo_ecgs/{filename}', dpi=150, bbox_inches='tight')
    plt.close()

generate_ecg('Normal', 'normal.png')
generate_ecg('STEMI', 'stemi.png')
generate_ecg('AFib', 'afib.png')
generate_ecg('VTach', 'vtach.png')
generate_ecg('Bradycardia', 'bradycardia.png')
generate_ecg('LBBB', 'lbbb.png')

print("Demo ECGs generated.")
