import streamlit as st
import pandas as pd
import io

# --- CORE LOGIC (Updated for Continuous Numbering) ---
def process_discharge_data(df, filename, start_cycle_num=0):
    """
    Detects discharge cycles using Peak-to-Zero logic.
    start_cycle_num: The starting number for the first cycle (e.g., 0, 1000, etc.)
    """
    # 1. Auto-detect columns
    cols = df.columns
    time_col = next((c for c in cols if 'ime' in c), None) 
    volt_col = next((c for c in cols if 'oltage' in c or 'otential' in c), None)

    if not time_col or not volt_col:
        return None, f"Error in {filename}: Could not detect 'Time' or 'Voltage' columns."

    # 2. Sort Data
    df = df.sort_values(by=time_col).reset_index(drop=True)
    times = df[time_col].values
    volts = df[volt_col].values
    count = len(volts)
    
    peaks_arr = [] 
    zeros_arr = [] 
    
    # State Flag
    looking_for_peak = True
    
    # EDGE CHECK: Index 0 (Left Edge)
    if count > 1 and volts[0] > 0.5 and volts[0] > volts[1]:
        peaks_arr.append(times[0])
        looking_for_peak = False

    # MAIN LOOP (3-Pointer)
    for i in range(1, count - 1):
        current_v = volts[i]
        current_t = times[i]
        
        if looking_for_peak:
            prev_v = volts[i-1]
            next_v = volts[i+1]
            # Peak Logic
            if (current_v > prev_v) and (current_v > next_v) and current_v > 0.5:
                peaks_arr.append(current_t)
                looking_for_peak = False 
        else:
            # Zero Logic
            if current_v <= 0.05:
                zeros_arr.append(current_t)
                looking_for_peak = True 

    # EDGE CHECK: Last Index (Right Edge)
    if not looking_for_peak: 
        if volts[-1] <= 0.05:
            zeros_arr.append(times[-1])

    # CALCULATE
    min_len = min(len(peaks_arr), len(zeros_arr))
    cycles_data = []
    
    for k in range(min_len):
        start = peaks_arr[k]
        end = zeros_arr[k]
        
        duration_minutes = end - start
        duration_seconds = duration_minutes * 60
        
        # --- LOGIC UPDATE: Use the starting offset ---
        # If start_cycle_num is 1000, the first cycle here becomes 1001
        actual_cycle_number = (k + 1) + start_cycle_num
        
        cycles_data.append({
            'Source_File': filename,
            'Cycle Number': actual_cycle_number,
            'Discharge Time (Seconds)': duration_seconds
        })
        
    return pd.DataFrame(cycles_data), None

# --- FRONTEND UI ---
st.set_page_config(page_title="Batch Discharge Analyzer", page_icon="⚡", layout="wide")

st.title("⚡ Batch Battery Analyzer (Continuous Numbering)")
st.markdown("""
**Upload multiple files.** The cycle numbering will continue from one file to the next (e.g., File 1: 1-1000, File 2: 1001-2000).
""")

uploaded_files = st.file_uploader("Upload Data Files", type=["xlsx", "csv"], accept_multiple_files=True)

if uploaded_files:
    all_files_data = []
    summary_stats = []
    
    # --- NEW: Global Counter ---
    current_cycle_count = 0 
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    if st.button(f"Analyze {len(uploaded_files)} Files"):
        
        # Sort files by name so the order is predictable (File1, File2, File3...)
        # This ensures 1001 comes after 1000, not random order.
        sorted_files = sorted(uploaded_files, key=lambda x: x.name)
        
        for i, uploaded_file in enumerate(sorted_files):
            status_text.text(f"Processing file {i+1}/{len(sorted_files)}: {uploaded_file.name} (Starting at Cycle {current_cycle_count + 1})...")
            progress_bar.progress((i + 1) / len(sorted_files))
            
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                # --- PASS THE CURRENT COUNT ---
                result_df, error = process_discharge_data(df, uploaded_file.name, start_cycle_num=current_cycle_count)
                
                if error:
                    st.error(error)
                else:
                    all_files_data.append(result_df)
                    
                    # Update stats
                    num_new_cycles = len(result_df)
                    avg_time = result_df['Discharge Time (Seconds)'].mean()
                    
                    summary_stats.append({
                        "Filename": uploaded_file.name,
                        "Cycles Found": num_new_cycles,
                        "Range": f"{current_cycle_count + 1} - {current_cycle_count + num_new_cycles}",
                        "Avg Time (s)": round(avg_time, 2)
                    })
                    
                    # --- UPDATE COUNTER FOR NEXT FILE ---
                    current_cycle_count += num_new_cycles
                    
            except Exception as e:
                st.error(f"Failed to process {uploaded_file.name}: {e}")

        if all_files_data:
            st.success("Processing Complete!")
            status_text.empty()
            
            st.subheader("📊 Summary Statistics")
            summary_df = pd.DataFrame(summary_stats)
            st.dataframe(summary_df, use_container_width=True)
            
            master_df = pd.concat(all_files_data, ignore_index=True)
            
            st.subheader("📥 Download Master Data")
            csv = master_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download Master CSV",
                data=csv,
                file_name="continuous_cycle_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("No valid data found.")
