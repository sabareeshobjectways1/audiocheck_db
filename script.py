import streamlit as st
import pandas as pd
import numpy as np
import librosa
import os
from io import BytesIO
import math
from pathlib import Path

# Configure Streamlit page
st.set_page_config(
    page_title="WAV File Volume Analyzer",
    page_icon="🎵",
    layout="wide"
)

# Volume categories and their RMS ranges
VOLUME_CATEGORIES = {
    "soft": {"rms_range": "-35dB to -25dB", "min_db": -35, "max_db": -25},
    "comfortable": {"rms_range": "-25dB to -15dB", "min_db": -25, "max_db": -15}
}

def rms_to_db(rms_value):
    """Convert RMS value to dB"""
    if rms_value == 0:
        return -np.inf
    return 20 * math.log10(rms_value)

def extract_info_from_filename(filename):
    """Extract speaker ID and category from filename"""
    parts = filename.replace('.wav', '').split('_')
    speaker_id = "Unknown"
    category = "unknown"
    
    if len(parts) >= 3:
        speaker_id = parts[0]
        for part in parts:
            if part.lower() in ['soft', 'comfortable']:
                category = part.lower()
                break
    return speaker_id, category

def analyze_wav_file(file_path, filename):
    """Analyze a WAV file and return its properties"""
    try:
        speaker_id, expected_category = extract_info_from_filename(filename)
        y, sr = librosa.load(file_path, sr=None)
        rms = librosa.feature.rms(y=y)[0]
        rms_mean = np.mean(rms)
        db_value = rms_to_db(rms_mean)
        
        status = "Bad"
        db_range = "N/A"
        
        if expected_category in VOLUME_CATEGORIES:
            category_info = VOLUME_CATEGORIES[expected_category]
            db_range = category_info["rms_range"]
            if category_info["min_db"] <= db_value <= category_info["max_db"]:
                status = "Good"
        
        return {
            "Speaker_ID": speaker_id,
            "Filename": filename,
            "Category": expected_category,
            "Current_File_Db": round(db_value, 1),
            "Db_range": db_range,
            "Status": status
        }
    
    except Exception as e:
        speaker_id, expected_category = extract_info_from_filename(filename)
        st.error(f"Error processing {filename}: {str(e)}")
        return {
            "Speaker_ID": speaker_id,
            "Filename": filename,
            "Category": expected_category,
            "Current_File_Db": "Error",
            "Db_range": "Error",
            "Status": "Error"
        }

def scan_folders_from_path(root_path, selected_folders=None):
    """Scan folders from the given root path and process WAV files"""
    all_results = {}
    
    if not os.path.exists(root_path):
        st.error(f"Path does not exist: {root_path}")
        return all_results
    
    subdirs = [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
    
    if not subdirs:
        st.error(f"No folders found in: {root_path}")
        return all_results
    
    if selected_folders:
        subdirs_to_scan = [d for d in subdirs if d in selected_folders]
    else:
        subdirs_to_scan = subdirs

    for folder_name in subdirs_to_scan:
        folder_path = os.path.join(root_path, folder_name)
        wav_files = [os.path.join(root, file) for root, _, files in os.walk(folder_path) for file in files if file.lower().endswith('.wav')]
        
        if wav_files:
            folder_results = []
            progress_bar = st.progress(0, text=f"Processing folder: {folder_name}")
            
            for i, wav_file in enumerate(wav_files):
                filename = os.path.basename(wav_file)
                result = analyze_wav_file(wav_file, filename)
                folder_results.append(result)
                progress_bar.progress((i + 1) / len(wav_files), text=f"Processing folder: {folder_name}")
            
            progress_bar.empty()
            all_results[folder_name] = folder_results
        else:
            st.warning(f"No WAV files found in folder: {folder_name}")
            
    return all_results

def create_excel_report(results_data):
    """Create Excel report from analysis results in a single sheet."""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Create a summary sheet
        summary_data = []
        for folder_name, results in results_data.items():
            total_files = len(results)
            good_files = len([r for r in results if r['Status'] == 'Good'])
            bad_files = total_files - good_files
            
            summary_data.append({
                'Folder': folder_name,
                'Total Files': total_files,
                'Good Files': good_files,
                'Bad Files': bad_files,
                'Success Rate': f"{(good_files/total_files)*100:.1f}%" if total_files > 0 else "0%"
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Create a single sheet for all detailed results
        all_details_list = []
        for folder_name, results in results_data.items():
            if results:
                for result in results:
                    # Add the folder name to each result dictionary
                    result['Folder'] = folder_name 
                    all_details_list.append(result)

        if all_details_list:
            # Reformat the consolidated data for the DataFrame
            df_data = []
            for i, result in enumerate(all_details_list, 1):
                df_data.append({
                    'Sl.no': i,
                    'Folder': result.get('Folder', 'N/A'),
                    'speaker ID': result['Speaker_ID'],
                    'Filename': result['Filename'],
                    'category': result['Category'],
                    'Current_File_Db': result['Current_File_Db'],
                    'Db_range': result['Db_range'],
                    'Status': result['Status']
                })
            
            df_all_results = pd.DataFrame(df_data)
            df_all_results.to_excel(writer, sheet_name='Detailed_Results', index=False)

    output.seek(0)
    return output

# Streamlit UI
def main():
    st.title("🎵 WAV File Volume Analyzer")
    st.markdown("---")
    
    st.subheader("📂 Folder Path Configuration")
    
    root_path = st.text_input(
        "Enter the root path containing your audio folders:",
        placeholder="e.g., C:/Users/YourName/AudioData or /home/user/audio_data",
        help="The path should contain subfolders with WAV files"
    )
    
    if root_path and os.path.exists(root_path):
        try:
            available_folders = [d for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
            
            if available_folders:
                st.success(f"✅ Found {len(available_folders)} folders.")
                
                # Default selection is now all available folders
                selected_folders = st.multiselect(
                    "Select folders to analyze:",
                    options=available_folders,
                    default=available_folders, 
                    help="All folders are selected by default. You can deselect any you wish to exclude."
                )
                
                folders_to_process = selected_folders
                st.info(f"📊 Will process {len(folders_to_process)} folder(s): {', '.join(folders_to_process)}")
                
                if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
                    if not folders_to_process:
                        st.warning("Please select at least one folder to analyze.")
                    else:
                        with st.spinner("Scanning folders and analyzing WAV files..."):
                            results = scan_folders_from_path(root_path, folders_to_process)
                        
                        if results:
                            st.success("✅ Analysis completed!")
                            
                            # --- Results Display ---
                            st.subheader("📈 Analysis Summary")
                            summary_data = []
                            total_files_all, total_good_all = 0, 0
                            
                            for folder_name, folder_results in results.items():
                                total_files = len(folder_results)
                                good_files = len([r for r in folder_results if r['Status'] == 'Good'])
                                total_files_all += total_files
                                total_good_all += good_files
                                summary_data.append({
                                    'Folder': folder_name,
                                    'Total Files': total_files,
                                    'Good Files': good_files,
                                    'Bad Files': total_files - good_files,
                                    'Success Rate': f"{(good_files/total_files)*100:.1f}%" if total_files > 0 else "N/A"
                                })
                            
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(summary_df, use_container_width=True)
                            
                            overall_success_rate = (total_good_all / total_files_all * 100) if total_files_all > 0 else 0
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Total Files", total_files_all)
                            col2.metric("Good Files", total_good_all)
                            col3.metric("Bad Files", total_files_all - total_good_all)
                            col4.metric("Overall Success Rate", f"{overall_success_rate:.1f}%")
                            
                            st.subheader("📋 Detailed Results")
                            # Combine all results into one DataFrame for display
                            all_display_data = []
                            for folder_name, folder_results in results.items():
                                for result in folder_results:
                                    all_display_data.append({
                                        'Folder': folder_name,
                                        'Speaker ID': result['Speaker_ID'],
                                        'Filename': result['Filename'],
                                        'Category': result['Category'],
                                        'Current File dB': result['Current_File_Db'],
                                        'Status': result['Status']
                                    })
                            
                            if all_display_data:
                                display_df = pd.DataFrame(all_display_data)
                                st.dataframe(display_df, use_container_width=True)
                            
                            st.subheader("📊 Download Report")
                            excel_file = create_excel_report(results)
                            st.download_button(
                                label="📥 Download Excel Report",
                                data=excel_file,
                                file_name="wav_volume_analysis_report.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheet.sheet",
                                use_container_width=True
                            )
                        else:
                            st.error("❌ No processable WAV files were found in the selected folders.")
            else:
                st.error("❌ No sub-folders found in the specified path.")
                
        except Exception as e:
            st.error(f"❌ Error accessing the specified path: {str(e)}")
    
    elif root_path:
        st.error("❌ The specified path does not exist. Please check it and try again.")

if __name__ == "__main__":
    main()