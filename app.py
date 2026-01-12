import streamlit as st
import pandas as pd
import io

# --- CORE LOGIC (Verified) ---
def process_discharge_data(df):
    """
    detects discharge cycles using Peak-to-Zero logic.
    Returns a DataFrame with Cycle Number and Discharge Time (seconds).
    """
    # 1. Auto-detect columns
    cols = df.columns
    time_col = next((c for c in cols if 'ime' in c), None) 
    volt_col = next((c for c in cols if 'oltage' in c or 'otential' in c), None)

    if not time_col or not volt_col:
        return None, f"Could not detect 'Time' or 'Voltage' columns. Found: {list(cols)}"

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
            # Peak Logic: Mid > Left AND Mid > Right
            if (current_v > prev_v) and (current_v > next_v) and current_v > 0.5:
                peaks_arr.append(current_t)
                looking_for_peak = False 
        else:
            # Zero Logic: Voltage <= 0.05 (Permissive zero)
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
        
        # Multiply by 60 to convert Minutes -> Seconds
        duration_minutes = end - start
        duration_seconds = duration_minutes * 60
        
        cycles_data.append({
            'Cycle Number': k + 1,
            'Discharge Time (Seconds)': duration_seconds
        })
        
    return pd.DataFrame(cycles_data), None

# --- FRONTEND UI ---
st.set_page_config(page_title="Discharge Analyzer", page_icon="🔋")

st.title("🔋 Battery Discharge Analyzer")
st.markdown("""
**For Researchers:** Upload your raw Voltage-Time data (.csv or .xlsx). 
The app will extract the exact discharge duration for every cycle (in seconds).
""")

uploaded_file = st.file_uploader("Upload Data File", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        # Load File
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success(f"File uploaded successfully! ({len(df)} rows)")

        if st.button("Analyze Cycles"):
            with st.spinner("Processing..."):
                result_df, error = process_discharge_data(df)
            
            if error:
                st.error(error)
            else:
                st.subheader(f"Results: Found {len(result_df)} Cycles")
                st.dataframe(result_df.head())
                
                # Convert to CSV for download
                csv = result_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="Download Results CSV",
                    data=csv,
                    file_name="discharge_times_seconds.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.error(f"An error occurred: {e}")