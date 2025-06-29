import streamlit as st
import pandas as pd
import os

# Set wide mode
st.set_page_config(layout="wide", page_title="Sheet Cutting & Scrap Inventory")

# Initial Sheet Size
SHEET_WIDTH = 1250  # in mm
SHEET_LENGTH = 2500  # in mm

# Unit Conversion Mapping
unit_conversion = {
    'mm': 1,
    'cm': 10,
    'inch': 25.4,
    'feet': 304.8,
    'meter': 1000,
    'sut': 3
}

# Load existing data or create new ones
expected_order_cols = ['Order ID', 'Required Width (mm)', 'Required Length (mm)', 'Gauge', 'Quantity', 'Cut Direction', 'Source', 'Scrap ID Used', 'Sheet Number', 'Weight (kg)', 'Price per KG', 'Total Cost']
expected_scrap_cols = ['Scrap ID', 'Width (mm)', 'Length (mm)', 'Gauge', 'Available', 'Weight (kg)', 'Price per KG', 'Total Cost']

if os.path.exists('orders.csv'):
    orders_df = pd.read_csv('orders.csv')
    if list(orders_df.columns) != expected_order_cols:
        st.warning("orders.csv format is outdated. Resetting file...")
        os.remove('orders.csv')
        orders_df = pd.DataFrame(columns=expected_order_cols)
else:
    orders_df = pd.DataFrame(columns=expected_order_cols)

if os.path.exists('scraps.csv'):
    scraps_df = pd.read_csv('scraps.csv')
    if list(scraps_df.columns) != expected_scrap_cols:
        st.warning("scraps.csv format is outdated. Resetting file...")
        os.remove('scraps.csv')
        scraps_df = pd.DataFrame(columns=expected_scrap_cols)
else:
    scraps_df = pd.DataFrame(columns=expected_scrap_cols)

if not orders_df.empty and 'Sheet Number' in orders_df.columns:
    sheet_count = orders_df['Sheet Number'].max() if pd.notnull(orders_df['Sheet Number']).any() else 0
else:
    sheet_count = 0

scraps_df['Width (mm)'] = pd.to_numeric(scraps_df['Width (mm)'], errors='coerce')
scraps_df['Length (mm)'] = pd.to_numeric(scraps_df['Length (mm)'], errors='coerce')
scraps_df['Gauge'] = pd.to_numeric(scraps_df['Gauge'], errors='coerce')

# Calculate weight function
def calculate_weight(width, length, gauge):
    return (width * length * gauge * 7.85) / 1000

# Find scrap that fits
def find_scrap(width, length, gauge):
    global scraps_df

    available_scraps = scraps_df[(scraps_df['Available'] == 'Yes') & (scraps_df['Gauge'] == gauge) & (scraps_df['Width (mm)'] >= width) & (scraps_df['Length (mm)'] >= length)]

    if not available_scraps.empty:
        available_scraps = available_scraps.copy()
        available_scraps['Area'] = available_scraps['Width (mm)'] * available_scraps['Length (mm)']
        best_scrap = available_scraps.sort_values('Area').iloc[0]
        best_scrap_id = best_scrap['Scrap ID']
        scrap_index = scraps_df[scraps_df['Scrap ID'] == best_scrap_id].index[0]
        return best_scrap_id, scrap_index

    return None, None

# Add scrap to inventory
def add_scrap(width, length, gauge, scrap_price_per_kg):
    global scraps_df
    scrap_id = len(scraps_df) + 1
    weight = calculate_weight(width, length, gauge)
    total_cost = weight * scrap_price_per_kg
    new_scrap = pd.DataFrame([{
        'Scrap ID': scrap_id,
        'Width (mm)': width,
        'Length (mm)': length,
        'Gauge': gauge,
        'Available': 'Yes',
        'Weight (kg)': weight,
        'Price per KG': scrap_price_per_kg,
        'Total Cost': total_cost
    }])
    scraps_df = pd.concat([scraps_df, new_scrap], ignore_index=True)

# Process new order
def process_order(order_id, required_width, width_unit, required_length, length_unit, gauge, quantity, cut_direction, order_price_per_kg, scrap_price_per_kg):
    global orders_df, scraps_df, sheet_count

    required_width_mm = required_width * unit_conversion[width_unit]
    required_length_mm = required_length * unit_conversion[length_unit]

    for _ in range(quantity):
        scrap_id, scrap_index = find_scrap(required_width_mm, required_length_mm, gauge)

        if scrap_id is not None:
            scrap = scraps_df.iloc[scrap_index]
            sheet_width = scrap['Width (mm)']
            sheet_length = scrap['Length (mm)']

            if cut_direction == 'Width First':
                scrap1_width = sheet_width - required_width_mm
                scrap1_length = sheet_length

                scrap2_width = required_width_mm
                scrap2_length = sheet_length - required_length_mm

            elif cut_direction == 'Height First':
                scrap1_width = sheet_width
                scrap1_length = sheet_length - required_length_mm

                scrap2_width = sheet_width - required_width_mm
                scrap2_length = required_length_mm
            else:
                st.error("Invalid cutting direction selected.")
                return

            scraps_df.at[scrap_index, 'Available'] = 'No'
            source = 'Scrap'

        else:
            sheet_count += 1
            sheet_width = SHEET_WIDTH
            sheet_length = SHEET_LENGTH

            if cut_direction == 'Width First':
                scrap1_width = SHEET_WIDTH - required_width_mm
                scrap1_length = SHEET_LENGTH

                scrap2_width = required_width_mm
                scrap2_length = SHEET_LENGTH - required_length_mm

            elif cut_direction == 'Height First':
                scrap1_width = SHEET_WIDTH
                scrap1_length = SHEET_LENGTH - required_length_mm

                scrap2_width = SHEET_WIDTH - required_width_mm
                scrap2_length = required_length_mm
            else:
                st.error("Invalid cutting direction selected.")
                return

            source = 'New Sheet'

        if scrap1_width > 0 and scrap1_length > 0:
            add_scrap(scrap1_width, scrap1_length, gauge, scrap_price_per_kg)

        if scrap2_width > 0 and scrap2_length > 0:
            add_scrap(scrap2_width, scrap2_length, gauge, scrap_price_per_kg)

        weight = calculate_weight(required_width_mm, required_length_mm, gauge)
        total_cost = weight * order_price_per_kg

        new_order = pd.DataFrame([{
            'Order ID': order_id,
            'Required Width (mm)': required_width_mm,
            'Required Length (mm)': required_length_mm,
            'Gauge': gauge,
            'Quantity': 1,
            'Cut Direction': cut_direction,
            'Source': source,
            'Scrap ID Used': scrap_id if scrap_id is not None else '',
            'Sheet Number': sheet_count if scrap_id is None else '',
            'Weight (kg)': weight,
            'Price per KG': order_price_per_kg,
            'Total Cost': total_cost
        }])

        orders_df = pd.concat([orders_df, new_order], ignore_index=True)

# Clear all data
def clear_inventory():
    global orders_df, scraps_df, sheet_count
    orders_df = pd.DataFrame(columns=expected_order_cols)
    scraps_df = pd.DataFrame(columns=expected_scrap_cols)
    sheet_count = 0
    if os.path.exists('orders.csv'):
        os.remove('orders.csv')
    if os.path.exists('scraps.csv'):
        os.remove('scraps.csv')

# Streamlit App UI
st.title("Sheet Cutting & Scrap Inventory")

if st.button('🗑️ Clear All Inventory and Orders'):
    clear_inventory()
    st.warning("All inventory and orders have been cleared!")

col_left, col_right = st.columns([1, 4])

with col_left:
    st.header("📋 Enter New Order")

    with st.form(key='order_form'):
        order_id = len(orders_df) + 1

        col1, col2 = st.columns([2, 1])
        with col1:
            required_width = st.number_input('Required Width', min_value=1, step=1)
        with col2:
            width_unit = st.selectbox('Width Unit', ['mm', 'cm', 'inch', 'feet', 'meter', 'sut'])

        col3, col4 = st.columns([2, 1])
        with col3:
            required_length = st.number_input('Required Length', min_value=1, step=1)
        with col4:
            length_unit = st.selectbox('Length Unit', ['mm', 'cm', 'inch', 'feet', 'meter', 'sut'])

        gauge = int(st.selectbox('Select Gauge', ['10', '12', '14', '16', '18', '20', '22', '24']))
        quantity = st.number_input('Quantity Required', min_value=1, step=1)
        cut_direction = st.selectbox('Select Cutting Direction', ['Width First', 'Height First'])

        order_price_per_kg = st.number_input('Price per KG for Order', min_value=0.0, step=0.1)
        scrap_price_per_kg = st.number_input('Price per KG for Scrap', min_value=0.0, step=0.1)

        submit_button = st.form_submit_button(label='Process Order')

    if submit_button:
      if required_width <= 0:
        st.error("Required Width must be greater than 0.")
      elif required_length <= 0:
        st.error("Required Length must be greater than 0.")
      else:
        process_order(order_id, required_width, width_unit, required_length, length_unit, gauge, quantity, cut_direction, order_price_per_kg, scrap_price_per_kg)
        orders_df.to_csv('orders.csv', index=False)
        scraps_df.to_csv('scraps.csv', index=False)
        st.success(f"Order {order_id} processed successfully! {quantity} pieces processed.")

with col_right:
    st.header("📑 Current Orders")
    st.dataframe(orders_df, use_container_width=True)

    st.markdown("---")
    st.header("🧩 Available Scrap Inventory")
    available_scraps = scraps_df[scraps_df['Available'] == 'Yes']
    st.dataframe(available_scraps, use_container_width=True)

    st.markdown("---")
    st.header("📊 Dashboard Summary")

    total_sheets_used = orders_df[orders_df['Source'] == 'New Sheet']['Sheet Number'].nunique()
    total_scraps = available_scraps.shape[0]
    total_scrap_area = available_scraps.apply(lambda x: x['Width (mm)'] * x['Length (mm)'], axis=1).sum()
    total_scrap_weight = available_scraps['Weight (kg)'].sum()
    total_scrap_cost = available_scraps['Total Cost'].sum()

    if total_sheets_used > 0:
        total_sheet_area_used = total_sheets_used * SHEET_WIDTH * SHEET_LENGTH
        scrap_percentage = (total_scrap_area / total_sheet_area_used) * 100
    else:
        scrap_percentage = 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric(label="🗒️ Total Sheets Used", value=total_sheets_used)
    with col2:
        st.metric(label="🧩 Total Scrap Pieces", value=total_scraps)
    with col3:
        st.metric(label="📐 Total Scrap Area (mm²)", value=int(total_scrap_area))
    with col4:
        st.metric(label="♻️ Scrap %", value=f"{scrap_percentage:.2f}%")
    with col5:
        st.metric(label="⚖️ Total Scrap Weight (kg)", value=f"{total_scrap_weight:.0f}")
    with col6:
        st.metric(label="💰 Total Scrap Cost", value=f"{total_scrap_cost:.0f}")
