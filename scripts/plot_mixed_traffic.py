import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap

def analyze_fcd_data(trajectories):
    """Analyze FCD data to determine key parameters."""
    all_speeds = np.concatenate([data['speed'] for data in trajectories.values()])
    all_positions = np.concatenate([data['adjusted_pos'] for data in trajectories.values()])
    
    speed_min = np.min(all_speeds)
    speed_max = np.max(all_speeds)
    road_length = 1000.0  # Fixed total road length
    
    print("\nData Analysis:")
    print(f"Number of vehicles: {len(trajectories)}")
    print(f"Speed range: {speed_min:.2f} to {speed_max:.2f} m/s")
    print(f"Road length: {road_length:.2f} m")
    
    return speed_min, speed_max, road_length

def adjust_position(pos, lane):
    """Adjust position based on lane type to create continuous 1000m road."""
    if 'a_0' in lane:  # First edge
        return pos
    elif 'b_0' in lane:  # Second edge
        return pos + 900  # Shift b_0 positions by 900m
    return pos

def parse_fcd_file(file_path):
    """Parse SUMO's FCD output file and extract vehicle trajectories.
    
    The FCD file contains vehicle positions at each timestep (every 0.1s).
    Each vehicle has an ID, type, position, speed, and other attributes.
    """
    trajectories = defaultdict(lambda: {'time': [], 'pos': [], 'adjusted_pos': [], 'speed': [], 'type': None, 'lane': []})
    
    # Parse XML file iteratively
    for event, elem in ET.iterparse(file_path, events=('end',)):
        if elem.tag == 'timestep':
            time = float(elem.get('time'))
            for vehicle in elem.findall('vehicle'):
                veh_id = vehicle.get('id')
                pos = float(vehicle.get('pos'))
                speed = float(vehicle.get('speed'))
                veh_type = vehicle.get('type')
                lane = vehicle.get('lane')
                
                # Calculate adjusted position based on lane
                adjusted_pos = adjust_position(pos, lane)
                
                trajectories[veh_id]['time'].append(time)
                trajectories[veh_id]['pos'].append(pos)
                trajectories[veh_id]['adjusted_pos'].append(adjusted_pos)
                trajectories[veh_id]['speed'].append(speed)
                trajectories[veh_id]['lane'].append(lane)
                if trajectories[veh_id]['type'] is None:
                    trajectories[veh_id]['type'] = veh_type
            
            # Clear element to save memory
            elem.clear()
    
    # Convert lists to numpy arrays
    for veh_id in trajectories:
        for key in ['time', 'pos', 'adjusted_pos', 'speed']:
            trajectories[veh_id][key] = np.array(trajectories[veh_id][key])
    
    return trajectories

def plot_time_space_diagram(trajectories):
    """Create time-space diagram from vehicle trajectories using scatter plots."""
    # Fixed parameters from simulation configuration
    road_length = 1000.0  # meters (total length of both edges)
    sim_start = 0
    sim_end = 600  # seconds (from sumocfg)
    
    # Analyze data to get speed range
    speed_min, speed_max, _ = analyze_fcd_data(trajectories)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(15, 10))
    plt.rcParams.update({'font.size': 12})
    
    # Set white background
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    
    # Create custom colormap (red=stop, yellow=medium, green=max speed)
    colors = [(0.8, 0, 0), (1, 1, 0), (0, 0.8, 0)]  # red, yellow, green
    n_bins = 100
    cmap = LinearSegmentedColormap.from_list("custom", colors, N=n_bins)
    
    # Collect all data points
    all_points = []
    for veh_id, data in trajectories.items():
        times = data['time']
        positions = data['adjusted_pos']  # Use adjusted positions
        speeds = data['speed']
        
        # Add all points
        for i in range(len(times)):
            all_points.append((positions[i], times[i], speeds[i]))
    
    # Sort points by position (ascending) so higher positions are plotted last
    all_points.sort()
    
    # Separate sorted points back into arrays
    positions = np.array([p[0] for p in all_points])
    times = np.array([p[1] for p in all_points])
    speeds = np.array([p[2] for p in all_points])
    
    # Create scatter plot with speed-based colors
    scatter = ax.scatter(times, positions, 
                        c=speeds, 
                        cmap=cmap,
                        vmin=0, 
                        vmax=speed_max, 
                        s=5,  # Point size
                        alpha=0.6)  # Transparency
    
    # Print vehicle info
    for veh_id, data in sorted(trajectories.items()):
        print(f"Vehicle {veh_id}: t={data['time'][0]:.1f}-{data['time'][-1]:.1f}s, "
              f"speed={np.min(data['speed']):.1f}-{np.max(data['speed']):.1f} m/s, "
              f"lane={data['lane'][0]}")
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Speed [m/s]', fontsize=12)
    cbar.ax.tick_params(labelsize=10)
    
    # Set fixed axis limits
    ax.set_xlim(sim_start, sim_end)
    ax.set_ylim(0, road_length)
    ax.set_xlabel('Time [s]', fontsize=12)
    ax.set_ylabel('Position [m]', fontsize=12)
    
    # Configure grid
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    
    # Set tick marks every 100s for time and 200m for position
    ax.set_xticks(np.arange(sim_start, sim_end + 1, 100))
    ax.set_yticks(np.arange(0, road_length + 1, 200))
    ax.tick_params(labelsize=10)
    
    # Add title with actual speed range
    plt.title(f'Vehicle Trajectories in Ring Road\n'
              f'Speed Range: {speed_min:.1f} - {speed_max:.1f} m/s\n'
              'Red = Stopped, Yellow = Medium Speed, Green = Free Flow', 
              fontsize=14, pad=10)
    
    # Adjust layout and save
    plt.tight_layout()
    plt.savefig('time_space_mixed.png', dpi=300, bbox_inches='tight')
    plt.close()

def main():
    fcd_file = 'output_fcd.xml'
    
    print("Parsing FCD file...")
    trajectories = parse_fcd_file(fcd_file)
    
    print("\nCreating time-space diagram...")
    plot_time_space_diagram(trajectories)
    
    print("\nPlot saved as time_space_mixed.png")

if __name__ == "__main__":
    main()