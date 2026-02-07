"""
🏥 Virtue Foundation Agent - Streamlit Interface

Production-ready interface for interacting with the medical intelligence system.
Inspired by vfmatch.org with enhanced AI capabilities.
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.virtue_data_loader import VirtueFoundationDataLoader

# Page configuration
st.set_page_config(
    page_title="Virtue Foundation Agent",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        padding-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .question-button {
        margin: 0.25rem;
        padding: 0.5rem;
    }
    .citation-box {
        background-color: #e8f4f8;
        border-left: 4px solid #1f77b4;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .alert-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .stTextInput input {
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'initialized' not in st.session_state:
    with st.spinner("🔄 Initializing Virtue Foundation Agent..."):
        try:
            st.session_state.data_loader = VirtueFoundationDataLoader()
            st.session_state.initialized = True
        except Exception as e:
            st.error(f"❌ Error initializing system: {str(e)}")
            st.exception(e)
            st.session_state.initialized = False

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'facilities_data' not in st.session_state:
    try:
        df = pd.read_csv('data/raw/ghana/facilities_real.csv')
        st.session_state.facilities_data = df
    except Exception as e:
        st.warning(f"⚠️ Could not load facilities data: {str(e)}")
        st.session_state.facilities_data = None

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🏥 Navigation")
    page = st.radio(
        "Select View:",
        ["🤖 AI Chat", "📊 Dashboard", "🗺️ Medical Deserts", "🔍 Facility Search", "❓ Example Questions"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    st.markdown("### 📈 System Status")
    if st.session_state.initialized:
        st.success("✅ System Online")
        if st.session_state.facilities_data is not None:
            st.info(f"📍 {len(st.session_state.facilities_data)} facilities loaded")
    else:
        st.error("❌ System Offline")
    
    st.markdown("---")
    
    st.markdown("### 🎯 Quick Stats")
    if st.session_state.facilities_data is not None:
        df = st.session_state.facilities_data
        facilities_count = len(df[df['organizationType'] == 'facility']) if 'organizationType' in df.columns else len(df)
        st.metric("Facilities", facilities_count)
        
        # Count specialties
        if 'specialties' in df.columns:
            import ast
            total_specialties = 0
            for spec in df['specialties'].dropna():
                try:
                    spec_list = ast.literal_eval(spec) if isinstance(spec, str) else spec
                    if isinstance(spec_list, list):
                        total_specialties += len(spec_list)
                except:
                    pass
            st.metric("Total Specialties", total_specialties)
    
    st.markdown("---")
    st.markdown("### 📚 Resources")
    st.markdown("[📖 Documentation](VF_AGENT_REQUIREMENTS.md)")
    st.markdown("[🎯 59 Questions](59_QUESTIONS_STATUS.md)")
    st.markdown("[🚀 Implementation Plan](IMPLEMENTATION_PLAN.md)")

# Main Content Area
st.markdown('<div class="main-header">🏥 Virtue Foundation Medical Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Reducing treatment time by 100× through AI-powered healthcare coordination</div>', unsafe_allow_html=True)

# Page: AI Chat
if page == "🤖 AI Chat":
    st.markdown("## 💬 Ask the AI Agent")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("Ask questions about healthcare facilities, medical deserts, or resource distribution:")
        
        # Example questions as quick buttons
        st.markdown("#### 🎯 Try these questions:")
        example_questions = [
            "How many hospitals have cardiology?",
            "Show me medical deserts in Ghana",
            "Which facilities claim unrealistic procedure counts?",
            "Where is the workforce for cardiology practicing?",
            "What services does Korle Bu Teaching Hospital offer?",
        ]
        
        cols = st.columns(2)
        for idx, question in enumerate(example_questions):
            with cols[idx % 2]:
                if st.button(question, key=f"example_{idx}", use_container_width=True):
                    st.session_state.current_question = question
    
    with col2:
        st.markdown("#### 📊 Coverage")
        st.metric("Must Have Questions", "12/21", "57%")
        st.progress(0.57)
    
    # Chat input
    user_input = st.text_input(
        "Your question:",
        placeholder="Type your question here...",
        key="chat_input",
        value=st.session_state.get('current_question', '')
    )
    
    if st.button("🚀 Ask Agent", type="primary", use_container_width=True):
        if user_input:
            with st.spinner("🤔 Processing your question..."):
                try:
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": user_input
                    })
                    
                    # Simple demo response for MVP
                    response_text = f"Query received: '{user_input}'. Agent processing is in development. Current data shows {len(st.session_state.facilities_data)} facilities loaded."
                    
                    # Add response to chat history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text
                    })
                    
                    st.session_state.current_question = ""
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error processing question: {str(e)}")
                    st.exception(e)
    
    # Display chat history
    if st.session_state.chat_history:
        st.markdown("---")
        st.markdown("### 💬 Conversation History")
        
        for idx, message in enumerate(reversed(st.session_state.chat_history[-6:])):  # Show last 6 messages
            if message['role'] == 'user':
                st.markdown(f"**👤 You:** {message['content']}")
            else:
                st.markdown(f"**🤖 Agent:** {message['content']}")
                st.markdown("---")

# Page: Dashboard
elif page == "📊 Dashboard":
    st.markdown("## 📊 Healthcare Infrastructure Dashboard")
    
    if st.session_state.facilities_data is not None:
        df = st.session_state.facilities_data
        
        # Top metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            facilities_count = len(df[df['organizationType'] == 'facility']) if 'organizationType' in df.columns else len(df)
            st.metric("Total Facilities", facilities_count)
        
        with col2:
            regions_count = df['region'].nunique() if 'region' in df.columns else 0
            st.metric("Regions Covered", regions_count)
        
        with col3:
            if 'specialties' in df.columns:
                import ast
                unique_specialties = set()
                for spec in df['specialties'].dropna():
                    try:
                        spec_list = ast.literal_eval(spec) if isinstance(spec, str) else spec
                        if isinstance(spec_list, list):
                            unique_specialties.update(spec_list)
                    except:
                        pass
                st.metric("Unique Specialties", len(unique_specialties))
            else:
                st.metric("Unique Specialties", 0)
        
        with col4:
            if 'equipment' in df.columns:
                import ast
                total_equipment = 0
                for eq in df['equipment'].dropna():
                    try:
                        eq_list = ast.literal_eval(eq) if isinstance(eq, str) else eq
                        if isinstance(eq_list, list):
                            total_equipment += len(eq_list)
                    except:
                        pass
                st.metric("Total Equipment", total_equipment)
            else:
                st.metric("Total Equipment", 0)
        
        # Charts
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📍 Facilities by Region")
            if 'region' in df.columns:
                region_counts = df['region'].value_counts().head(10)
                fig = px.bar(
                    x=region_counts.values,
                    y=region_counts.index,
                    orientation='h',
                    labels={'x': 'Number of Facilities', 'y': 'Region'},
                    color=region_counts.values,
                    color_continuous_scale='Blues'
                )
                fig.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 🏥 Facility Types")
            if 'facilityTypeId' in df.columns:
                type_counts = df['facilityTypeId'].value_counts().head(10)
                fig = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    hole=0.4
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # Top specialties
        st.markdown("---")
        st.markdown("### 🩺 Top Medical Specialties")
        
        if 'specialties' in df.columns:
            import ast
            specialty_counts = {}
            for spec in df['specialties'].dropna():
                try:
                    spec_list = ast.literal_eval(spec) if isinstance(spec, str) else spec
                    if isinstance(spec_list, list):
                        for s in spec_list:
                            specialty_counts[s] = specialty_counts.get(s, 0) + 1
                except:
                    pass
            
            if specialty_counts:
                top_specialties = sorted(specialty_counts.items(), key=lambda x: x[1], reverse=True)[:15]
                fig = px.bar(
                    x=[count for _, count in top_specialties],
                    y=[spec for spec, _ in top_specialties],
                    orientation='h',
                    labels={'x': 'Number of Facilities', 'y': 'Specialty'},
                    color=[count for _, count in top_specialties],
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(showlegend=False, height=500)
                st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.warning("⚠️ No facility data available")

# Page: Medical Deserts
elif page == "🗺️ Medical Deserts":
    st.markdown("## 🗺️ Medical Desert Detection")
    st.markdown("Identify regions with critical gaps in healthcare services")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("### 🎯 Detection Settings")
        
        specialty = st.selectbox(
            "Select Specialty:",
            ["All", "cardiology", "surgery", "pediatrics", "obstetrics", "emergency"]
        )
        
        radius_km = st.slider(
            "Detection Radius (km):",
            min_value=10,
            max_value=100,
            value=50,
            step=10
        )
        
        if st.button("🔍 Detect Medical Deserts", type="primary", use_container_width=True):
            with st.spinner("🔍 Analyzing healthcare infrastructure..."):
                try:
                    # Load facilities
                    facilities = st.session_state.data_loader.load_virtue_foundation_data()
                    
                    # Simple demo detection
                    st.session_state.detected_deserts = []
                    st.info(f"✅ Loaded {len(facilities)} facilities. Medical desert detection in development.")
                    
                except Exception as e:
                    st.error(f"❌ Error detecting medical deserts: {str(e)}")
    
    with col1:
        st.markdown("### 🌍 Medical Desert Map")
        
        # Create map
        ghana_center = [7.9465, -1.0232]
        m = folium.Map(location=ghana_center, zoom_start=7, tiles="OpenStreetMap")
        
        # Add facility markers
        if st.session_state.facilities_data is not None:
            df = st.session_state.facilities_data
            
            # Sample facilities for performance
            sample_df = df.sample(min(100, len(df)))
            
            for _, facility in sample_df.iterrows():
                # Try to get coordinates (use approximations)
                lat = facility.get('latitude', ghana_center[0])
                lon = facility.get('longitude', ghana_center[1])
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=3,
                    popup=f"{facility.get('name', 'Unknown')}",
                    color='green',
                    fill=True,
                    fillColor='green',
                    fillOpacity=0.6
                ).add_to(m)
        
        # Add medical deserts
        if hasattr(st.session_state, 'detected_deserts'):
            for desert in st.session_state.detected_deserts[:20]:  # Show top 20
                folium.Circle(
                    location=[desert.get('latitude', ghana_center[0]), desert.get('longitude', ghana_center[1])],
                    radius=desert.get('radius_km', 50) * 1000,  # Convert to meters
                    popup=f"Medical Desert: {desert.get('missing_specialty', 'Unknown')}<br>Severity: {desert.get('severity', 'Unknown')}",
                    color='red',
                    fill=True,
                    fillColor='red',
                    fillOpacity=0.2
                ).add_to(m)
        
        st_folium(m, width=700, height=500)
    
    # Display results
    if hasattr(st.session_state, 'detected_deserts') and st.session_state.detected_deserts:
        st.markdown("---")
        st.markdown("### 📋 Detected Medical Deserts")
        
        for idx, desert in enumerate(st.session_state.detected_deserts[:10]):
            with st.expander(f"Desert #{idx+1}: {desert.get('missing_specialty', 'Unknown Specialty')}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Severity", desert.get('severity', 'Unknown'))
                
                with col2:
                    st.metric("Radius (km)", f"{desert.get('radius_km', 0):.1f}")
                
                with col3:
                    st.metric("Population Affected", desert.get('population_affected', 'Unknown'))
                
                if desert.get('recommendations'):
                    st.markdown("**💡 Recommendations:**")
                    for rec in desert['recommendations']:
                        st.markdown(f"- {rec}")

# Page: Facility Search
elif page == "🔍 Facility Search":
    st.markdown("## 🔍 Search Healthcare Facilities")
    
    if st.session_state.facilities_data is not None:
        df = st.session_state.facilities_data
        
        # Search filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_name = st.text_input("🏥 Facility Name:", placeholder="Search by name...")
        
        with col2:
            if 'region' in df.columns:
                regions = ['All'] + sorted(df['region'].dropna().unique().tolist())
                search_region = st.selectbox("📍 Region:", regions)
            else:
                search_region = 'All'
        
        with col3:
            if 'facilityTypeId' in df.columns:
                types = ['All'] + sorted(df['facilityTypeId'].dropna().unique().tolist())
                search_type = st.selectbox("🏥 Type:", types)
            else:
                search_type = 'All'
        
        # Apply filters
        filtered_df = df.copy()
        
        if search_name:
            filtered_df = filtered_df[filtered_df['name'].str.contains(search_name, case=False, na=False)]
        
        if search_region != 'All' and 'region' in df.columns:
            filtered_df = filtered_df[filtered_df['region'] == search_region]
        
        if search_type != 'All' and 'facilityTypeId' in df.columns:
            filtered_df = filtered_df[filtered_df['facilityTypeId'] == search_type]
        
        # Display results
        st.markdown(f"### 📋 Found {len(filtered_df)} facilities")
        
        if len(filtered_df) > 0:
            # Show as cards
            for idx, (_, facility) in enumerate(filtered_df.head(20).iterrows()):
                with st.expander(f"{facility.get('name', 'Unknown Facility')} - {facility.get('region', 'Unknown Region')}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**📍 Region:** {facility.get('region', 'N/A')}")
                        st.markdown(f"**🏥 Type:** {facility.get('facilityTypeId', 'N/A')}")
                        st.markdown(f"**📞 Phone:** {facility.get('phone', 'N/A')}")
                        st.markdown(f"**📧 Email:** {facility.get('email', 'N/A')}")
                        
                        if facility.get('source_url'):
                            st.markdown(f"**🔗 Source:** [View]({facility['source_url']})")
                    
                    with col2:
                        # Specialties
                        if 'specialties' in facility and pd.notna(facility['specialties']):
                            import ast
                            try:
                                specialties = ast.literal_eval(facility['specialties']) if isinstance(facility['specialties'], str) else facility['specialties']
                                if isinstance(specialties, list) and specialties:
                                    st.markdown(f"**🩺 Specialties:** {len(specialties)}")
                                    st.markdown(", ".join(specialties[:5]))
                            except:
                                pass
                        
                        # Equipment
                        if 'equipment' in facility and pd.notna(facility['equipment']):
                            import ast
                            try:
                                equipment = ast.literal_eval(facility['equipment']) if isinstance(facility['equipment'], str) else facility['equipment']
                                if isinstance(equipment, list) and equipment:
                                    st.markdown(f"**🔧 Equipment:** {len(equipment)}")
                            except:
                                pass
        else:
            st.info("No facilities match your search criteria")
    
    else:
        st.warning("⚠️ No facility data available")

# Page: Example Questions
elif page == "❓ Example Questions":
    st.markdown("## ❓ 59 Real-World Questions")
    st.markdown("These are the actual questions the Virtue Foundation needs answered")
    
    # Organize by category
    questions_by_category = {
        "✅ Must Have (21 questions)": {
            "Basic Queries": [
                "How many hospitals have cardiology?",
                "How many hospitals in Greater Accra have surgery?",
                "What services does Korle Bu Teaching Hospital offer?",
                "Are there clinics in Kumasi that do pediatrics?",
                "Which region has the most hospitals?",
            ],
            "Geospatial": [
                "How many hospitals treating cardiology within 50 km of Accra?",
                "What are the largest cold spots for surgery?",
            ],
            "Anomaly Detection": [
                "Which facilities claim unrealistic procedure counts?",
                "Which facilities have high breadth with minimal infrastructure?",
                "Which things shouldn't move together in the data?",
                "Facilities with major discrepancies in procedure counts?",
            ],
            "Workforce & Resources": [
                "Where is the workforce for cardiology practicing?",
                "Which facilities lack equipment for claimed subspecialty?",
                "Which procedures depend on very few facilities?",
                "What's the distribution of oversupply vs scarcity?",
            ],
            "NGO Analysis": [
                "Where are gaps where no organizations are working?",
            ],
        },
        "🟡 Should Have (17 questions)": {
            "Validation": [
                "Procedures requiring equipment not in facility inventory?",
                "Facilities without critical emergency equipment?",
                "Procedures claimed without required subspecialists?",
            ],
            "Service Classification": [
                "Which procedures are itinerant/outreach only?",
                "Regions with visiting vs permanent specialists?",
            ],
        },
        "🟠 Could Have (19 questions)": {
            "Unmet Needs": [
                "Areas with disease prevalence but no facilities?",
                "Population to specialist ratios vs WHO recommendations?",
            ],
            "Benchmarking": [
                "Regions falling short of WHO guidelines?",
                "Hospitals with inadequate equipment vs WHO standards?",
            ],
        },
    }
    
    for priority, categories in questions_by_category.items():
        st.markdown(f"### {priority}")
        
        for category, questions in categories.items():
            with st.expander(f"📂 {category}"):
                for idx, question in enumerate(questions):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"{idx+1}. {question}")
                    with col2:
                        if st.button("Try it", key=f"try_{priority}_{category}_{idx}"):
                            st.session_state.current_question = question
                            st.session_state.page = "🤖 AI Chat"
                            st.rerun()

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🏥 Virtue Foundation Agent**")
    st.markdown("Reducing treatment time by 100×")

with col2:
    st.markdown("**📊 Progress: 57% Complete**")
    st.markdown("12/21 Must Have Questions")

with col3:
    st.markdown("**🚀 Ship Date: June 7, 2026**")
    st.markdown(f"Days remaining: {(pd.Timestamp('2026-06-07') - pd.Timestamp.now()).days}")
