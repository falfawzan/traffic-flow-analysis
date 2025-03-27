import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.colors import LinearSegmentedColormap

def parse_fcd_file(file_path):
    """Parse SUMO's FCD output file and extract vehicle trajectories with continuous positions."""
    trajectories = defaultdict(lambda: {'time': [], 'pos': [], 'speed': [], 'lane': [], 'type': None})
    main_circle_length = 901.53  # Length of edge a_0
    total_length = 1000.0
    
    for event, elem in ET.iterparse(file_path, events=('end',)):
        if elem.tag == 'timestep':
            time = float(elem.get('time'))
            for vehicle in elem.findall('vehicle'):
                veh_id = vehicle.get('id')
                lane = vehicle.get('lane')
                raw_pos = float(vehicle.get('pos'))
                speed = float(vehicle.get('speed'))
                veh_type = vehicle.get('type')
                
                # Store vehicle type
                if trajectories[veh_id]['type'] is None:
                    trajectories[veh_id]['type'] = 'regular' if 'regular' in veh_type else 'stable'
                
                # Calculate continuous position based on lane
                if lane == 'b_0':
                    # When on connector (b_0), add position to main circle length
                    pos = main_circle_length + raw_pos
                else:
                    pos = raw_pos
                
                # Get previous position if it exists
                if trajectories[veh_id]['pos']:
                    prev_pos = trajectories[veh_id]['pos'][-1]
                    # Handle wrapping around
                    if prev_pos > pos + total_length/2:
                        # Vehicle wrapped around to beginning
                        pos += total_length
                
                trajectories[veh_id]['time'].append(time)
                trajectories[veh_id]['pos'].append(pos)
                trajectories[veh_id]['speed'].append(speed)
                trajectories[veh_id]['lane'].append(lane)
            
            elem.clear()
    
    # Convert lists to numpy arrays and handle wrapping
    for veh_id in trajectories:
        for key in ['time', 'pos', 'speed']:
            trajectories[veh_id][key] = np.array(trajectories[veh_id][key])
            
        # Ensure positions are properly wrapped within road length
        positions = trajectories[veh_id]['pos']
        times = trajectories[veh_id]['time']
        
        # Adjust positions to be continuous across laps
        for i in range(1, len(positions)):
            if positions[i] < positions[i-1] - total_length/2:
                # Vehicle completed a lap, adjust all subsequent positions
                positions[i:] += total_length
    
    return trajectories

def calculate_macroscopic_quantities(trajectories, dx=10, dt=10, total_length=1000, veh_type=None):
    """Calculate macroscopic quantities using Edie's definitions for specific vehicle type."""
    # Find time range
    all_times = []
    for vid, data in trajectories.items():
        if veh_type is None or data['type'] == veh_type:
            all_times.extend(data['time'])
    t_min, t_max = min(all_times), max(all_times)
    
    # Create grid for space-time windows
    x_bins = np.arange(0, total_length + dx, dx)
    t_bins = np.arange(t_min, t_max + dt, dt)
    
    # Initialize arrays for macroscopic quantities
    density = np.zeros((len(t_bins)-1, len(x_bins)-1))
    flow = np.zeros_like(density)
    speed = np.zeros_like(density)
    
    # Process each space-time cell
    for t_idx in range(len(t_bins)-1):
        t_start, t_end = t_bins[t_idx], t_bins[t_idx+1]
        
        for x_idx in range(len(x_bins)-1):
            x_start, x_end = x_bins[x_idx], x_bins[x_idx+1]
            
            total_time_spent = 0    # Total time spent by vehicles in cell
            total_distance = 0      # Total distance traveled by vehicles in cell
            vehicles_crossed = 0    # Count of vehicles that crossed the cell
            
            # Process each vehicle of the specified type
            for veh_id, data in trajectories.items():
                if veh_type is not None and data['type'] != veh_type:
                    continue
                    
                # Find points within and around the time window
                time_mask = (data['time'] >= t_start - dt) & (data['time'] <= t_end + dt)
                if not np.any(time_mask):
                    continue
                
                times = data['time'][time_mask]
                positions = data['pos'][time_mask] % total_length  # Wrap positions
                speeds = data['speed'][time_mask]
                
                # Interpolate to get more precise entry/exit times
                if len(times) > 1:
                    # Interpolate position at cell boundaries
                    t_interp = np.interp([x_start, x_end], positions, times, 
                                       left=np.nan, right=np.nan)
                    
                    # Check if vehicle was in the cell during the time window
                    mask = (positions >= x_start) & (positions < x_end)
                    cell_times = times[mask]
                    cell_positions = positions[mask]
                    
                    if len(cell_times) > 0:
                        # Calculate time spent in cell
                        time_in_cell = min(t_end, cell_times[-1]) - max(t_start, cell_times[0])
                        if time_in_cell > 0:
                            total_time_spent += time_in_cell
                            
                            # Calculate distance traveled in cell
                            pos_start = max(x_start, cell_positions[0])
                            pos_end = min(x_end, cell_positions[-1])
                            distance = pos_end - pos_start
                            if distance > 0:
                                total_distance += distance
                        
                        # Count vehicle crossings
                        if not np.isnan(t_interp).all():
                            vehicles_crossed += 1
            
            # Calculate macroscopic quantities for the cell
            area = dx * dt  # Space-time area of the cell
            
            # Density: total time spent / area [veh/m]
            if area > 0:
                density[t_idx, x_idx] = total_time_spent / area
            
            # Flow: vehicles crossed per unit time [veh/s]
            if dt > 0:
                flow[t_idx, x_idx] = vehicles_crossed / dt
            
            # Speed: total distance / total time [m/s]
            if total_time_spent > 0:
                speed[t_idx, x_idx] = total_distance / total_time_spent
    
    # Convert units
    density *= 1000  # Convert to veh/km
    flow *= 3600    # Convert to veh/hr
    speed *= 3.6    # Convert to km/h
    
    return density, flow, speed, t_bins[:-1], x_bins[:-1]

def plot_macroscopic_quantity(quantity, t_bins, x_bins, title, vmin=None, vmax=None, veh_type=""):
    """Plot a macroscopic quantity as a space-time contour."""
    fig, ax = plt.subplots(figsize=(12, 8))
    plt.rcParams.update({'font.size': 12})
    
    # Custom colormap - reversed for density and flow, normal for speed
    colors_normal = [(0.8, 0, 0), (1, 1, 0), (0, 0.8, 0)]  # red, yellow, green
    colors_reversed = [(0, 0.8, 0), (1, 1, 0), (0.8, 0, 0)]  # green, yellow, red
    
    if 'Speed' in title:
        cmap = LinearSegmentedColormap.from_list("custom", colors_normal, N=100)
    else:  # For density and flow
        cmap = LinearSegmentedColormap.from_list("custom", colors_reversed, N=100)
    
    # Calculate data range if not provided
    if vmin is None:
        vmin = np.nanmin(quantity)
    if vmax is None:
        vmax = np.nanmax(quantity)
    
    # Create the contour plot
    mesh = plt.pcolormesh(t_bins, x_bins, quantity.T, cmap=cmap, vmin=vmin, vmax=vmax)
    
    # Add colorbar
    cbar = plt.colorbar(mesh)
    cbar.set_label(title, fontsize=12)
    cbar.ax.tick_params(labelsize=10)
    
    # Set labels and title
    plt.xlabel('Time [s]', fontsize=12)
    plt.ylabel('Space [m]', fontsize=12)
    veh_type_str = f" ({veh_type} vehicles)" if veh_type else ""
    plt.title(f'Space-Time Evolution of {title}{veh_type_str}', fontsize=14, pad=10)
    
    # Configure grid
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.gca().set_axisbelow(True)
    
    # Set tick parameters
    plt.tick_params(labelsize=10)
    
    plt.tight_layout()

def main():
    fcd_file = 'output_fcd.xml'
    
    print("Parsing FCD file...")
    trajectories = parse_fcd_file(fcd_file)
    
    # Process all vehicles together
    print("\nCalculating macroscopic quantities for all vehicles...")
    density_all, flow_all, speed_all, t_bins, x_bins = calculate_macroscopic_quantities(trajectories)
    
    # Process regular vehicles
    print("Calculating macroscopic quantities for regular vehicles...")
    density_reg, flow_reg, speed_reg, _, _ = calculate_macroscopic_quantities(trajectories, veh_type='regular')
    
    # Process stable vehicles
    print("Calculating macroscopic quantities for stable vehicles...")
    density_stb, flow_stb, speed_stb, _, _ = calculate_macroscopic_quantities(trajectories, veh_type='stable')
    
    # Calculate and print data ranges for each vehicle type
    for veh_type, density, flow, speed in [
        ("All", density_all, flow_all, speed_all),
        ("Regular", density_reg, flow_reg, speed_reg),
        ("Stable", density_stb, flow_stb, speed_stb)
    ]:
        print(f"\n{veh_type} vehicles data ranges:")
        print(f"Density: {np.nanmin(density):.1f} to {np.nanmax(density):.1f} veh/km")
        print(f"Flow: {np.nanmin(flow):.1f} to {np.nanmax(flow):.1f} veh/hr")
        print(f"Speed: {np.nanmin(speed):.1f} to {np.nanmax(speed):.1f} km/h")
    
    print("\nCreating plots...")
    # Plot for all vehicles
    for veh_type, density, flow, speed, suffix in [
        ("All", density_all, flow_all, speed_all, "all"),
        ("Regular", density_reg, flow_reg, speed_reg, "regular"),
        ("Stable", density_stb, flow_stb, speed_stb, "stable")
    ]:
        # Plot density
        density_max = np.nanpercentile(density, 99)
        plot_macroscopic_quantity(density, t_bins, x_bins, 'Density [veh/km]', 
                                vmin=0, vmax=density_max, veh_type=veh_type)
        plt.savefig(f'density_contour_{suffix}.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Plot flow
        flow_max = np.nanpercentile(flow, 99)
        plot_macroscopic_quantity(flow, t_bins, x_bins, 'Flow [veh/hr]', 
                                vmin=0, vmax=flow_max, veh_type=veh_type)
        plt.savefig(f'flow_contour_{suffix}.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Plot speed
        speed_min = np.nanpercentile(speed, 1)
        speed_max = np.nanpercentile(speed, 99)
        plot_macroscopic_quantity(speed, t_bins, x_bins, 'Speed [km/h]', 
                                vmin=speed_min, vmax=speed_max, veh_type=veh_type)
        plt.savefig(f'speed_contour_{suffix}.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    print("\nPlots saved with suffixes _all, _regular, and _stable")

if __name__ == "__main__":
    main() 