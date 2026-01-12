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
st.set_page_config(page_title="Battery Studio", page_icon="⚡", layout="wide")

# Custom CSS for minor styling tweaks (Clean Header)
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E1E1E;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
    }
</style>
""", unsafe_allow_html=True)

# 1. SIDEBAR
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3103/3103446.png", width=50) # Generic battery icon
    st.markdown("## Control Panel")
    
    uploaded_files = st.file_uploader("📂 Upload Experiment Files", type=["xlsx", "csv"], accept_multiple_files=True)
    
    st.divider()
    
    with st.expander("ℹ️ How to use"):
        st.markdown("""
        1. **Select Files:** Upload multiple `.csv` or `.xlsx` files.
        2. **Auto-Naming:** Ensure filenames contain the cycle range (e.g., `Data_1001-2000.csv`).
        3. **Process:** Click the blue button to analyze.
        """)
        
    st.caption("v2.1 | CycleLab Pro")

# Initialize Session State
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None
if 'summary_stats' not in st.session_state:
    st.session_state.summary_stats = None

if not uploaded_files:
    st.session_state.processed_results = None
    st.session_state.summary_stats = None

# --- MAIN HERO SECTION ---
st.markdown('<div class="main-header">⚡ CycleLab Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Cycle Life Analysis & Degradation Tracking</div>', unsafe_allow_html=True)

if uploaded_files:
    # ACTION BAR
    col_run, col_info = st.columns([1, 2])
    
    with col_run:
        run_btn = st.button(f"▶ Process {len(uploaded_files)} Files", type="primary")
    
    with col_info:
        st.write("") # Alignment spacer
    
    if run_btn:
        temp_results = []
        temp_stats = []
        
        # --- NEW: Modern Status Container ---
        with st.status("Processing data...", expanded=True) as status:
            
            sorted_files = sorted(uploaded_files, key=lambda x: get_start_cycle_from_name(x.name))
            progress_bar = st.progress(0)
            
            for i, uploaded_file in enumerate(sorted_files):
                st.write(f"Analyzing **{uploaded_file.name}**...") # Logs inside the box
                
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
                        temp_results.append({"filename": uploaded_file.name, "df": result_df})
                        
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
                
                progress_bar.progress((i + 1) / len(sorted_files))

            status.update(label="Analysis Complete!", state="complete", expanded=False)

        st.session_state.processed_results = temp_results
        st.session_state.summary_stats = temp_stats
        st.toast("Processing finished successfully!", icon="✅") # Nice popup notification

    # --- RESULTS DASHBOARD ---
    if st.session_state.processed_results:
        
        st.divider()
        
        # 1. METRICS
        total_files = len(st.session_state.summary_stats)
        total_cycles = sum(item['Cycles Found'] for item in st.session_state.summary_stats)
        
        all_dfs = [item['df'] for item in st.session_state.processed_results]
        master_df = pd.concat(all_dfs, ignore_index=True).sort_values(by="Cycle Number")
        global_avg = master_df['Discharge Time (Seconds)'].mean()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Files", total_files)
        m2.metric("Total Cycles", f"{total_cycles:,}")
        m3.metric("Avg Discharge Time", f"{global_avg:.2f} s")
        m4.metric("Dataset Range", f"Cycle {master_df['Cycle Number'].min()} - {master_df['Cycle Number'].max()}")
        
        st.write("") # Spacer

        # 2. TABS
        tab_viz, tab_data, tab_dl = st.tabs(["📈 Visualization", "📊 Summary Data", "📂 Downloads"])
        
        # TAB 1: Visualization (Improved Styling)
        with tab_viz:
            st.subheader("Degradation Curve")
            
            fig = px.scatter(
                master_df, 
                x="Cycle Number", 
                y="Discharge Time (Seconds)",
                color="Source_File", 
                title="",
                labels={"Discharge Time (Seconds)": "Time (s)"},
                hover_data=["Discharge Time (Seconds)"]
            )
            # Make it look scientific (White background, grid lines)
            fig.update_layout(
                template="plotly_white",
                xaxis_title="Cycle Number",
                yaxis_title="Discharge Time (Seconds)",
                legend_title_text="Experiment File",
                height=500
            )
            fig.update_traces(marker=dict(size=6, opacity=0.8)) # Make dots nicer
            st.plotly_chart(fig, use_container_width=True)

        # TAB 2: Data Table
        with tab_data:
            st.subheader("File Statistics")
            summary_df = pd.DataFrame(st.session_state.summary_stats)
            st.dataframe(
                summary_df.style.highlight_max(axis=0, subset=['Avg Time (s)']), # Highlight best performer
                use_container_width=True
            )

        # TAB 3: Downloads
        with tab_dl:
            col_left, col_right = st.columns([1, 1])
            
            with col_left:
                st.markdown("### 📦 Master Dataset")
                st.caption("Combined data for all processed files.")
                csv_master = master_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Full Dataset (.csv)",
                    data=csv_master,
                    file_name="master_discharge_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )
                
            with col_right:
                st.markdown("### 📄 Individual Files")
                st.caption("Original files processed with cycle numbers.")
                
                # Scrollable container for many files
                with st.container(height=300):
                    for item in st.session_state.processed_results:
                        fname = item['filename']
                        csv_single = item['df'].to_csv(index=False).encode('utf-8')
                        
                        # Compact row
                        c1, c2 = st.columns([3, 1])
                        c1.text(fname)
                        c2.download_button("⬇", csv_single, f"processed_{fname}.csv", "text/csv", key=fname)

else:
    # Empty State Hero
    st.info("👋 Upload files from the sidebar to begin analysis.")
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Section_of_a_lithium-ion_battery.jpg/800px-Section_of_a_lithium-ion_battery.jpg", caption="Lithium-Ion Battery Structure", width=400)
