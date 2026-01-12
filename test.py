import streamlit as st
import pandas as pd
import io
import re

# --- HELPER: Extract Start Number from Filename ---
def get_start_cycle_from_name(filename):
    """
    Looks for the first number in the filename to use as the start cycle.
    Example: "V-T 1001-2000.xlsx" -> Returns 1001
    """
    # Find all sequences of digits
    numbers = re.findall(r'\d+', filename)
    if numbers:
        # Return the first number found (converted to integer)
        return int(numbers[0])
    return 1 # Default to 1 if no number found

# --- CORE LOGIC ---
def process_discharge_data(df, filename, forced_start_cycle=None):
    """
    Detects discharge cycles.
    forced_start_cycle: If provided, starts counting from this number.
    """
    cols = df.columns
    time_col = next((c for c in cols if 'ime' in c), None) 
    volt_col = next((c for c in cols if 'oltage' in c or 'otential' in c), None)

    if not time_col or not volt_col:
        return None, f"Error in {filename}: Could not detect columns."

    df = df.sort_values(by=time_col).reset_index(drop=True)
    times = df[time_col].values
    volts = df[volt_col].values
    count = len(volts)
    
    peaks_arr = [] 
    zeros_arr = [] 
    looking_for_peak = True
    
    # Left Edge
    if count > 1 and volts[0] > 0.5 and volts[0] > volts[1]:
        peaks_arr.append(times[0])
        looking_for_peak = False

    # Main Loop
    for i in range(1, count - 1):
        current_v = volts[i]
        current_t = times[i]
        
        if looking_for_peak:
            prev_v = volts[i-1]
            next_v = volts[i+1]
            if (current_v > prev_v) and (current_v > next_v) and current_v > 0.5:
                peaks_arr.append(current_t)
                looking_for_peak = False 
        else:
            if current_v <= 0.05:
                zeros_arr.append(current_t)
                looking_for_peak = True 

    # Right Edge
    if not looking_for_peak: 
        if volts[-1] <= 0.05:
            zeros_arr.append(times[-1])

    # Calculate
    min_len = min(len(peaks_arr), len(zeros_arr))
    cycles_data = []
    
    # DETERMINE STARTING NUMBER
    # If we parsed a number from the filename, use that. 
    # Otherwise fallback to 1.
    start_num = forced_start_cycle if forced_start_cycle is not None else 1
    
    for k in range(min_len):
        start = peaks_arr[k]
        end = zeros_arr[k]
        duration_seconds = (end - start) * 60
        
        # Use the specific start number + k
        actual_cycle_number = start_num + k
        
        cycles_data.append({
            'Source_File': filename,
            'Cycle Number': actual_cycle_number,
            'Discharge Time (Seconds)': duration_seconds
        })
        
    return pd.DataFrame(cycles_data), None

# --- FRONTEND UI ---
st.set_page_config(page_title="Batch Discharge Analyzer", page_icon="⚡", layout="wide")

st.title("⚡ Batch Battery Analyzer")
st.markdown("""
**Upload multiple files.** The app detects the cycle range from the filename (e.g., "1001-2000" starts at 1001).
""")

# Initialize Session State
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None
if 'summary_stats' not in st.session_state:
    st.session_state.summary_stats = None

uploaded_files = st.file_uploader("Upload Data Files", type=["xlsx", "csv"], accept_multiple_files=True)

if not uploaded_files:
    st.session_state.processed_results = None
    st.session_state.summary_stats = None

if uploaded_files:
    if st.button(f"Analyze {len(uploaded_files)} Files"):
        
        temp_results = []
        temp_stats = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # SORTING FIX: Sort files numerically based on the first number in the name
        # This fixes the "10001 comes before 1001" issue
        sorted_files = sorted(uploaded_files, key=lambda x: get_start_cycle_from_name(x.name))
        
        for i, uploaded_file in enumerate(sorted_files):
            status_text.text(f"Processing {uploaded_file.name}...")
            progress_bar.progress((i + 1) / len(sorted_files))
            
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                # 1. EXTRACT START NUMBER FROM FILENAME
                start_from_name = get_start_cycle_from_name(uploaded_file.name)
                
                # 2. PROCESS WITH FORCED START NUMBER
                result_df, error = process_discharge_data(df, uploaded_file.name, forced_start_cycle=start_from_name)
                
                if error:
                    st.error(error)
                else:
                    temp_results.append({
                        "filename": uploaded_file.name,
                        "df": result_df
                    })
                    
                    num_new_cycles = len(result_df)
                    # Calculate range based on what was actually generated
                    first_cycle = result_df['Cycle Number'].min()
                    last_cycle = result_df['Cycle Number'].max()
                    avg_time = result_df['Discharge Time (Seconds)'].mean()
                    
                    temp_stats.append({
                        "Filename": uploaded_file.name,
                        "Cycles Found": num_new_cycles,
                        "Range": f"{first_cycle} - {last_cycle}",
                        "Avg Time (s)": round(avg_time, 2)
                    })
                    
            except Exception as e:
                st.error(f"Failed to process {uploaded_file.name}: {e}")

        st.session_state.processed_results = temp_results
        st.session_state.summary_stats = temp_stats
        
        status_text.empty()
        st.success("Processing Complete!")

    # --- DISPLAY BLOCK ---
    if st.session_state.processed_results:
        
        st.subheader("📊 Summary Statistics")
        summary_df = pd.DataFrame(st.session_state.summary_stats)
        st.dataframe(summary_df, use_container_width=True)
        
        st.divider()

        col_master, col_indiv = st.columns([1, 1])
        
        with col_master:
            st.subheader("📥 Master Download")
            st.info("Contains all files merged into one.")
            
            all_dfs = [item['df'] for item in st.session_state.processed_results]
            master_df = pd.concat(all_dfs, ignore_index=True)
            # Optional: Sort Master by Cycle Number just in case
            master_df = master_df.sort_values(by="Cycle Number")
            
            csv_master = master_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Download Master CSV (All Data)",
                data=csv_master,
                file_name="master_discharge_results.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

        with col_indiv:
            st.subheader("📄 Individual Downloads")
            
            for item in st.session_state.processed_results:
                fname = item['filename']
                df_single = item['df']
                csv_single = df_single.to_csv(index=False).encode('utf-8')
                
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**{fname}**")
                with c2:
                    st.download_button(
                        label="Download",
                        data=csv_single,
                        file_name=f"processed_{fname}.csv",
                        mime="text/csv",
                        key=fname
                    )
                st.divider()
