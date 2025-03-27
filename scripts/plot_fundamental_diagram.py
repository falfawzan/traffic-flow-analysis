import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

def read_detector_data(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    data = {
        'flow': [],           # in veh/h
        'space_mean_speed': [],# in m/s (harmonic mean speed)
        'occupancy': [],      # in %
    }
    
    for interval in root.findall('interval'):
        if float(interval.get('harmonicMeanSpeed')) > 0:  # Filter out invalid measurements
            data['flow'].append(float(interval.get('flow')))
            data['space_mean_speed'].append(float(interval.get('harmonicMeanSpeed')))
            data['occupancy'].append(float(interval.get('occupancy')))
    
    # Convert to numpy arrays
    for key in data:
        data[key] = np.array(data[key])
    
    # Calculate density using q = ρ × v relationship
    # Convert speeds from m/s to km/h for consistency with flow (veh/h)
    space_mean_speed_kmh = data['space_mean_speed'] * 3.6  # Convert m/s to km/h
    data['density'] = data['flow'] / space_mean_speed_kmh  # veh/km
    
    return data

def greenshields_model(k, uf, kj):
    """Greenshields model for speed-density relationship"""
    return uf * (1 - k/kj)

def theoretical_curves(data):
    # Convert speeds to km/h for consistency
    space_mean_speed_kmh = data['space_mean_speed'] * 3.6
    
    # Estimate free flow speed (uf) from low density conditions
    low_density_mask = data['density'] < np.percentile(data['density'], 10)
    uf = np.max(space_mean_speed_kmh[low_density_mask])
    
    # Estimate jam density (kj) from high density conditions
    high_density_mask = data['density'] > np.percentile(data['density'], 90)
    kj = np.max(data['density']) * 1.1  # Add 10% margin
    
    # Fit Greenshields model to speed-density data
    try:
        popt, _ = curve_fit(lambda k, kj: greenshields_model(k, uf, kj), 
                           data['density'], 
                           space_mean_speed_kmh,
                           p0=[kj],
                           bounds=([50], [200]))
        kj = popt[0]
    except:
        # If fitting fails, use the estimated kj
        pass
    
    # Generate points for curves
    k = np.linspace(0, kj, 100)
    
    # Speed-density relationship (fitted Greenshields model)
    u = greenshields_model(k, uf, kj)
    
    # Flow-density relationship (q = k*u)
    q = k * u
    
    # Find capacity (maximum flow)
    qmax = np.max(q)
    
    # Find critical density (density at capacity)
    kcap = k[np.argmax(q)]
    
    # Find critical speed (speed at capacity)
    ucap = u[np.argmax(q)]
    
    return k, q, u, uf, qmax, kj, kcap, ucap

def plot_fundamental_diagrams(data):
    # Create theoretical curves
    k, q, u, uf, qmax, kj, kcap, ucap = theoretical_curves(data)
    
    # Create figure
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Fundamental Diagrams of Traffic Flow', fontsize=16, y=1.05)
    
    # Convert speeds to km/h
    space_mean_speed_kmh = data['space_mean_speed'] * 3.6
    
    # Common scatter plot parameters
    scatter_params = dict(c='blue', alpha=0.4, s=30)
    
    # 1. Flow-Density (q-k)
    ax1.scatter(data['density'], data['flow'], **scatter_params, label='Observed Data')
    ax1.plot(k, q, 'r-', linewidth=2, label='Fitted Model')
    ax1.set_xlabel('Density k (veh/km/lane)')
    ax1.set_ylabel('Flow q (veh/hour/lane)')
    ax1.grid(True, linestyle='--', alpha=0.7)
    # Add capacity point
    ax1.plot(kcap, qmax, 'y*', markersize=15, label='Capacity Point')
    ax1.axhline(y=qmax, color='y', linestyle='--', alpha=0.5)
    ax1.axvline(x=kcap, color='y', linestyle='--', alpha=0.5)
    ax1.text(kcap+2, qmax-200, f'kcap={kcap:.0f}', color='y')
    ax1.text(2, qmax+100, f'qmax={qmax:.0f}', color='y')
    ax1.legend()
    
    # 2. Speed-Flow (u-q)
    ax2.scatter(data['flow'], space_mean_speed_kmh, **scatter_params, label='Observed Data')
    ax2.plot(q, u, 'r-', linewidth=2, label='Fitted Model')
    ax2.set_xlabel('Flow q (veh/hour/lane)')
    ax2.set_ylabel('Space-Mean Speed u (km/hour)')
    ax2.grid(True, linestyle='--', alpha=0.7)
    # Add capacity point
    ax2.plot(qmax, ucap, 'y*', markersize=15, label='Capacity Point')
    ax2.axhline(y=ucap, color='y', linestyle='--', alpha=0.5)
    ax2.text(0, ucap+2, f'ucap={ucap:.0f}', color='y')
    ax2.legend()
    
    # 3. Speed-Density (u-k)
    ax3.scatter(data['density'], space_mean_speed_kmh, **scatter_params, label='Observed Data')
    ax3.plot(k, u, 'r-', linewidth=2, label='Fitted Model')
    ax3.set_xlabel('Density k (veh/km/lane)')
    ax3.set_ylabel('Space-Mean Speed u (km/hour)')
    ax3.grid(True, linestyle='--', alpha=0.7)
    # Add free-flow speed and critical density lines
    ax3.axhline(y=uf, color='y', linestyle='--', alpha=0.5)
    ax3.axvline(x=kcap, color='y', linestyle='--', alpha=0.5)
    ax3.text(2, uf+2, f'uf={uf:.0f}', color='y')
    ax3.text(kj-10, 2, f'kj={kj:.0f}', color='y')
    ax3.legend()
    
    # Set axis limits with some margin
    margin = 1.1
    ax1.set_xlim(0, kj * margin)
    ax1.set_ylim(0, qmax * margin)
    ax2.set_xlim(0, qmax * margin)
    ax2.set_ylim(0, uf * margin)
    ax3.set_xlim(0, kj * margin)
    ax3.set_ylim(0, uf * margin)
    
    plt.tight_layout()
    plt.savefig('fundamental_diagrams.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    # Read detector data
    detector_file = 'output_detector.out.xml'
    print("Reading detector data...")
    data = read_detector_data(detector_file)
    
    # Create fundamental diagrams
    print("Creating fundamental diagrams...")
    plot_fundamental_diagrams(data)
    print("Plots saved as fundamental_diagrams.png")

if __name__ == "__main__":
    main() 