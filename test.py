import streamlit as st
import pandas as pd
import io

# --- CORE LOGIC (Verified 3-Pointer + Edge Checks) ---
def process_discharge_data(df, filename):
    """
    Detects discharge cycles using Peak-to-Zero logic.
    Returns a DataFrame with Cycle Number, Discharge Time (seconds), and Source Filename.
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
    # If file starts with a peak (High Voltage), capture it
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
            # Peak Logic: Mid > Left AND Mid > Right
            if (current_v > prev_v) and (current_v > next_v) and current_v > 0.5:
                peaks_arr.append(current_t)
                looking_for_peak = False 
        else:
            # Zero Logic: Voltage <= 0.05
            if current_v <= 0.05:
                zeros_arr.append(current_t)
                looking_for_peak = True 

    # EDGE CHECK: Last Index (Right Edge)
    # If file ends exactly at 0V, capture it
    if not looking_for_peak: 
        if volts[-1] <= 0.05:
            zeros_arr.append(times[-1])

    # CALCULATE
    min_len = min(len(peaks_arr), len(zeros_arr))
    cycles_data = []
    
    for k in range(min_len):
        start = peaks_arr[k]
        end = zeros_arr[k]
        
        # Multiply by 60 to convert Minutes -> Seconds
        duration_minutes = end - start
        duration_seconds = duration_minutes * 60
        
        cycles_data.append({
            'Source_File': filename,
            'Cycle Number': k + 1,
            'Discharge Time (Seconds)': duration_seconds
        })
        
    return pd.DataFrame(cycles_data), None

# --- FRONTEND UI ---
st.set_page_config(page_title="Batch Discharge Analyzer", page_icon="⚡", layout="wide")

st.title("⚡ Batch Battery Analyzer (Test Mode)")
st.markdown("""
**Upload multiple files at once.** The app will combine them into a single Master CSV and provide a summary table.
""")

# MULTI-FILE UPLOADER
uploaded_files = st.file_uploader("Upload Data Files (.csv or .xlsx)", type=["xlsx", "csv"], accept_multiple_files=True)

if uploaded_files:
    # Containers for results
    all_files_data = []
    summary_stats = []
    
    # UI Elements for progress
    progress_bar = st.progress(0)
    status_text = st.empty()

    # START BUTTON
    if st.button(f"Analyze {len(uploaded_files)} Files"):
        
        for i, uploaded_file in enumerate(uploaded_files):
            # Update Progress
            status_text.text(f"Processing file {i+1}/{len(uploaded_files)}: {uploaded_file.name}...")
            progress_bar.progress((i + 1) / len(uploaded_files))
            
            try:
                # Load File
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                # Process
                result_df, error = process_discharge_data(df, uploaded_file.name)
                
                if error:
                    st.error(error)
                else:
                    # Append to Master List
                    all_files_data.append(result_df)
                    
                    # Calculate Stats for Summary Table
                    avg_time = result_df['Discharge Time (Seconds)'].mean()
                    total_cycles = len(result_df)
                    summary_stats.append({
                        "Filename": uploaded_file.name,
                        "Total Cycles": total_cycles,
                        "Avg Discharge Time (s)": round(avg_time, 2)
                    })
                    
            except Exception as e:
                st.error(f"Failed to process {uploaded_file.name}: {e}")

        # --- DISPLAY RESULTS ---
        if all_files_data:
            st.success("Processing Complete!")
            status_text.empty()
            
            # 1. Show Summary Table
            st.subheader("📊 Summary Statistics")
            summary_df = pd.DataFrame(summary_stats)
            st.dataframe(summary_df, use_container_width=True)
            
            # 2. Create Master CSV
            master_df = pd.concat(all_files_data, ignore_index=True)
            
            st.subheader("📥 Download All Data")
            st.markdown("Download the combined data for all batteries in one click.")
            
            csv = master_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download Master CSV (All Files)",
                data=csv,
                file_name="batch_discharge_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("No valid data found in the uploaded files.")
