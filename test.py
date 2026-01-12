import streamlit as st
import pandas as pd
import io
import re
import plotly.express as px

# --- HELPER: Extract Start Number ---
def get_start_cycle_from_name(filename):
    numbers = re.findall(r'\d+', filename)
    if numbers:
        return int(numbers[0])
    return 1 

# --- CORE LOGIC (Unchanged) ---
def process_discharge_data(df, filename, forced_start_cycle=None):
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
    
    if count > 1 and volts[0] > 0.5 and volts[0] > volts[1]:
        peaks_arr.append(times[0])
        looking_for_peak = False

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

    if not looking_for_peak: 
        if volts[-1] <= 0.05:
            zeros_arr.append(times[-1])

    min_len = min(len(peaks_arr), len(zeros_arr))
    cycles_data = []
    
    start_num = forced_start_cycle if forced_start_cycle is not None else 1
    
    for k in range(min_len):
        start = peaks_arr[k]
        end = zeros_arr[k]
        duration_seconds = (end - start) * 60
        actual_cycle_number = start_num + k
        
        cycles_data.append({
            'Source_File': filename,
            'Cycle Number': actual_cycle_number,
            'Discharge Time (Seconds)': duration_seconds
        })
        
    return pd.DataFrame(cycles_data), None

# --- FRONTEND UI ---
st.set_page_config(page_title="CycleLab Pro", page_icon="🔋", layout="wide")

# 1. SIDEBAR (Controls & Help)
with st.sidebar:
    st.title("🔋 CycleLab Pro")
    st.write("Batch Analysis Tool for Battery Research")
    
    st.divider()
    
    uploaded_files = st.file_uploader("📂 Upload Data Files", type=["xlsx", "csv"], accept_multiple_files=True)
    
    st.info("""
    **How to use:**
    1. Select multiple files.
    2. Click 'Run Analysis'.
    3. View dashboards and download reports.
    
    *Note: Numbering is auto-detected from filenames.*
    """)

# Initialize Session State
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None
if 'summary_stats' not in st.session_state:
    st.session_state.summary_stats = None

# Logic to clear data if files are removed
if not uploaded_files:
    st.session_state.processed_results = None
    st.session_state.summary_stats = None

# --- MAIN AREA ---

if uploaded_files:
    # RUN BUTTON (In the main area, top)
    if st.button(f"🚀 Run Analysis on {len(uploaded_files)} Files", type="primary"):
        
        temp_results = []
        temp_stats = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Sort files numerically
        sorted_files = sorted(uploaded_files, key=lambda x: get_start_cycle_from_name(x.name))
        
        for i, uploaded_file in enumerate(sorted_files):
            status_text.text(f"Processing {uploaded_file.name}...")
            progress_bar.progress((i + 1) / len(sorted_files))
            
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                start_from_name = get_start_cycle_from_name(uploaded_file.name)
                result_df, error = process_discharge_data(df, uploaded_file.name, forced_start_cycle=start_from_name)
                
                if error:
                    st.error(error)
                else:
                    temp_results.append({
                        "filename": uploaded_file.name,
                        "df": result_df
                    })
                    
                    num_new_cycles = len(result_df)
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
        progress_bar.empty()
        st.success("✅ Analysis Complete!")

    # --- DISPLAY RESULTS ---
    if st.session_state.processed_results:
        
        # 1. METRICS ROW
        total_files = len(st.session_state.summary_stats)
        total_cycles = sum(item['Cycles Found'] for item in st.session_state.summary_stats)
        
        # Calculate global average
        all_dfs = [item['df'] for item in st.session_state.processed_results]
        master_df = pd.concat(all_dfs, ignore_index=True).sort_values(by="Cycle Number")
        global_avg = master_df['Discharge Time (Seconds)'].mean()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Files Processed", total_files)
        col2.metric("Total Cycles Detected", f"{total_cycles:,}")
        col3.metric("Global Avg Time", f"{global_avg:.2f} s")
        
        st.divider()

        # 2. TABS FOR CLEANER UI
        tab1, tab2, tab3 = st.tabs(["📊 Summary & Master Data", "📈 Visualizations", "📂 Individual Files"])
        
        # TAB 1: Summary Table + Master Download
        with tab1:
            st.subheader("Dataset Overview")
            summary_df = pd.DataFrame(st.session_state.summary_stats)
            st.dataframe(summary_df, use_container_width=True)
            
            st.write("") # Spacer
            csv_master = master_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Master CSV (Merged Data)",
                data=csv_master,
                file_name="master_discharge_results.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

        # TAB 2: Interactive Plot (New Feature!)
        with tab2:
            st.subheader("Cycle Degradation Analysis")
            st.info("Visualizing Discharge Time vs. Cycle Number. Drop-offs indicate battery aging.")
            
            # Plotly Chart
            fig = px.scatter(
                master_df, 
                x="Cycle Number", 
                y="Discharge Time (Seconds)",
                color="Source_File", # Color code by file
                title="Discharge Performance Over Time",
                hover_data=["Discharge Time (Seconds)"]
            )
            st.plotly_chart(fig, use_container_width=True)

        # TAB 3: Individual Downloads
        with tab3:
            st.subheader("Download Individual Reports")
            for item in st.session_state.processed_results:
                fname = item['filename']
                df_single = item['df']
                csv_single = df_single.to_csv(index=False).encode('utf-8')
                
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"📄 **{fname}**")
                with c2:
                    st.download_button(
                        label="Download CSV",
                        data=csv_single,
                        file_name=f"processed_{fname}.csv",
                        mime="text/csv",
                        key=fname
                    )
                st.divider()

else:
    # Welcome Screen when no files are uploaded
    st.markdown("""
    ### 👋 Welcome to CycleLab Pro
    Upload your raw battery data on the left sidebar to get started.
    
    **Features:**
    * Auto-detects cycles (Peak-to-Zero logic)
    * Smart Numbering (reads `1001-2000` from filename)
    * Interactive Degradation Graphs
    * Batch Processing
    """)
