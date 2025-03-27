import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from collections import defaultdict

def get_vehicle_types():
    """Get vehicle types from FCD file."""
    vehicle_types = {}
    tree = ET.parse('output_fcd.xml')
    root = tree.getroot()
    
    for timestep in root:
        for vehicle in timestep:
            vid = vehicle.get('id')
            vtype = vehicle.get('type')
            if vid not in vehicle_types:
                vehicle_types[vid] = 'regular' if 'regular' in vtype else 'stable'
    
    return vehicle_types

def greenshields_model(k, uf, kj):
    """Greenshields model for speed-density relationship"""
    return uf * (1 - k/kj)

def theoretical_curves(data):
    # Convert speeds to km/h for consistency
    space_mean_speed_kmh = np.array(data['speed']) * 3.6
    
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

def read_detector_data(filename):
    """Read detector data from XML file."""
    tree = ET.parse(filename)
    root = tree.getroot()
    
    data = {'flow': [], 'speed': [], 'density': [], 'time': []}
    
    for interval in root.findall('interval'):
        time = float(interval.get('begin'))
        flow = float(interval.get('flow', 0))
        speed = float(interval.get('harmonicMeanSpeed', 0))
        
        # Skip intervals with no data
        if speed <= 0:
            continue
        
        # Calculate density (veh/km) from flow (veh/h) and speed (m/s)
        # Convert speed to km/h for density calculation
        density = flow / (speed * 3.6) if speed > 0 else 0
        
        data['time'].append(time)
        data['flow'].append(flow)
        data['speed'].append(speed)
        data['density'].append(density)
    
    # Convert lists to numpy arrays
    for key in data:
        data[key] = np.array(data[key])
    
    return data

def plot_fundamental_diagrams(data):
    """Create fundamental diagrams with theoretical curves."""
    # Create theoretical curves
    k, q, u, uf, qmax, kj, kcap, ucap = theoretical_curves(data)
    
    # Create figure
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Fundamental Diagrams of Traffic Flow', fontsize=16, y=1.05)
    
    # Convert speeds to km/h for plotting
    space_mean_speed_kmh = data['speed'] * 3.6
    
    # Common scatter plot parameters
    scatter_params = dict(alpha=0.6, s=50)
    
    # 1. Flow-Density (q-k)
    scatter1 = ax1.scatter(data['density'], data['flow'], 
                          c=space_mean_speed_kmh, 
                          cmap='viridis',
                          **scatter_params,
                          label='Observed Data')
    ax1.plot(k, q, 'r-', linewidth=2, label='Greenshields Model')
    ax1.set_xlabel('Density (veh/km)')
    ax1.set_ylabel('Flow (veh/h)')
    ax1.set_title('Flow-Density Relationship')
    ax1.grid(True, alpha=0.3)
    plt.colorbar(scatter1, ax=ax1, label='Speed (km/h)')
    # Add capacity point
    ax1.plot(kcap, qmax, 'y*', markersize=15, label='Capacity Point')
    ax1.axhline(y=qmax, color='y', linestyle='--', alpha=0.5)
    ax1.axvline(x=kcap, color='y', linestyle='--', alpha=0.5)
    ax1.text(kcap+2, qmax-200, f'kcap={kcap:.0f}', color='y')
    ax1.text(2, qmax+100, f'qmax={qmax:.0f}', color='y')
    ax1.legend()
    
    # 2. Speed-Flow (u-q)
    scatter2 = ax2.scatter(data['flow'], space_mean_speed_kmh,
                          c=data['density'],
                          cmap='viridis',
                          **scatter_params,
                          label='Observed Data')
    ax2.plot(q, u, 'r-', linewidth=2, label='Greenshields Model')
    ax2.set_xlabel('Flow (veh/h)')
    ax2.set_ylabel('Speed (km/h)')
    ax2.set_title('Speed-Flow Relationship')
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=ax2, label='Density (veh/km)')
    # Add capacity point
    ax2.plot(qmax, ucap, 'y*', markersize=15, label='Capacity Point')
    ax2.axhline(y=ucap, color='y', linestyle='--', alpha=0.5)
    ax2.text(0, ucap+2, f'ucap={ucap:.0f}', color='y')
    ax2.legend()
    
    # 3. Speed-Density (u-k)
    scatter3 = ax3.scatter(data['density'], space_mean_speed_kmh,
                          c=data['flow'],
                          cmap='viridis',
                          **scatter_params,
                          label='Observed Data')
    ax3.plot(k, u, 'r-', linewidth=2, label='Greenshields Model')
    ax3.set_xlabel('Density (veh/km)')
    ax3.set_ylabel('Speed (km/h)')
    ax3.set_title('Speed-Density Relationship')
    ax3.grid(True, alpha=0.3)
    plt.colorbar(scatter3, ax=ax3, label='Flow (veh/h)')
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
    plt.savefig('fundamental_diagrams_mixed.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    print("Reading detector data...")
    data = read_detector_data('output_detector.out.xml')
    
    print("\nCreating fundamental diagrams...")
    plot_fundamental_diagrams(data)
    
    # Print summary statistics
    print("\nTraffic Flow Statistics:")
    print(f"Average speed: {np.mean(data['speed']):.2f} m/s")
    print(f"Average flow: {np.mean(data['flow']):.2f} veh/h")
    print(f"Average density: {np.mean(data['density']):.2f} veh/km")
    print(f"Maximum flow: {np.max(data['flow']):.2f} veh/h")
    print(f"Maximum density: {np.max(data['density']):.2f} veh/km")
    print(f"Free flow speed: {np.max(data['speed']):.2f} m/s")
    
    print("\nPlots saved as fundamental_diagrams_mixed.png")

if __name__ == "__main__":
    main() 