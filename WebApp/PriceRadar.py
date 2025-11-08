import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
from PIL import Image

# Konfiguracja strony
st.set_page_config(
    page_title="Tripsaver - Price Radar AI",
    #page_icon="assets/svg.svg",
    layout="wide"
)

st.title("Tripsaver - Price Radar AI")
st.markdown("Znajdź najlepsze okazje lotnicze z zaawansowanymi filtrami")

# Pobierz aktualny klucz cache (data)
def get_cache_key():
    """Zwraca aktualną datę, aby wymusić odświeżenie cache każdego dnia"""
    return datetime.now().strftime('%Y-%m-%d')

# Załaduj dane z codziennym cache
@st.cache_data(ttl=86400)  # 86400 sekund = 24 godziny
def load_data(cache_key):
    """Załaduj dane lotów. Parametr cache_key zapewnia codzienne odświeżanie."""
    url = "archive/multi_city_tickets.csv"
    df = pd.read_csv(url)
    
    # Konwertuj kolumny dat na datetime
    df['Departure Date'] = pd.to_datetime(df['Departure Date'])
    df['Return Date'] = pd.to_datetime(df['Return Date'])
    
    # Wyodrębnij dzień tygodnia
    days_translation = {
        'Monday': 'Poniedziałek',
        'Tuesday': 'Wtorek',
        'Wednesday': 'Środa',
        'Thursday': 'Czwartek',
        'Friday': 'Piątek',
        'Saturday': 'Sobota',
        'Sunday': 'Niedziela'
    }
    
    df['Departure Day'] = df['Departure Date'].dt.day_name().map(days_translation)
    df['Return Day'] = df['Return Date'].dt.day_name().map(days_translation)
    
    return df

@st.cache_data(ttl=86400)
def load_ai_deals(cache_key):
    """Załaduj dane ofert AI. Parametr cache_key zapewnia codzienne odświeżanie."""
    url = "archive/best_deals_detected.csv"
    df = pd.read_csv(url)
    
    # Konwertuj kolumny dat na datetime
    df['Departure Date'] = pd.to_datetime(df['Departure Date'])
    df['Return Date'] = pd.to_datetime(df['Return Date'])
    
    # Wyodrębnij dzień tygodnia
    days_translation = {
        'Monday': 'Poniedziałek',
        'Tuesday': 'Wtorek',
        'Wednesday': 'Środa',
        'Thursday': 'Czwartek',
        'Friday': 'Piątek',
        'Saturday': 'Sobota',
        'Sunday': 'Niedziela'
    }
    
    df['Departure Day'] = df['Departure Date'].dt.day_name().map(days_translation)
    df['Return Day'] = df['Return Date'].dt.day_name().map(days_translation)
    
    return df

@st.cache_data(ttl=86400)
def load_exotic_flights(cache_key):
    """Załaduj dane lotów egzotycznych. Parametr cache_key zapewnia codzienne odświeżanie."""
    url = "archive/exotic_flight_prices_raw.csv"
    df = pd.read_csv(url)
    
    # Mapuj nazwy kolumn do standardowego formatu
    df = df.rename(columns={
        'departure': 'Departure Date',
        'return': 'Return Date',
        'price': 'Total Price',
        'trip_days': 'Trip Duration (Days)',
        'arrival_airport': 'Destination',
        'DepartureCity': 'Outbound From',
        'DepartureCountry': 'Departure Country',
        'ArrivalCity': 'Arrival City',
        'ArrivalCountry': 'ArrivalCountry'
    })
    
    # Konwertuj kolumny dat na datetime (z obsługą błędów)
    df['Departure Date'] = pd.to_datetime(df['Departure Date'], errors='coerce')
    df['Return Date'] = pd.to_datetime(df['Return Date'], errors='coerce')
    
    # Usuń wiersze z błędnymi datami
    df = df.dropna(subset=['Departure Date', 'Return Date'])
    
    # Konwertuj cenę na numeric
    df['Total Price'] = pd.to_numeric(df['Total Price'], errors='coerce')
    
    # Konwertuj Trip Duration na int
    df['Trip Duration (Days)'] = pd.to_numeric(df['Trip Duration (Days)'], errors='coerce').fillna(0).astype(int)
    
    # Usuń wiersze z brakującymi cenami
    df = df.dropna(subset=['Total Price'])
    
    # Wyodrębnij dzień tygodnia
    days_translation = {
        'Monday': 'Poniedziałek',
        'Tuesday': 'Wtorek',
        'Wednesday': 'Środa',
        'Thursday': 'Czwartek',
        'Friday': 'Piątek',
        'Saturday': 'Sobota',
        'Sunday': 'Niedziela'
    }
    
    df['Departure Day'] = df['Departure Date'].dt.day_name().map(days_translation)
    df['Return Day'] = df['Return Date'].dt.day_name().map(days_translation)
    
    # Dodaj kolumnę Inbound To (dla lotów egzotycznych zakładamy powrót do tego samego miasta)
    df['Inbound To'] = df['Outbound From']
    
    # Upewnij się, że wszystkie wymagane kolumny są stringami gdzie potrzeba
    for col in ['Outbound From', 'Destination', 'ArrivalCountry', 'Inbound To']:
        if col in df.columns:
            df[col] = df[col].astype(str)
    
    return df

# Funkcja do tworzenia hierarchii kraj -> miasta
def create_destination_hierarchy(df):
    """Tworzy słownik z krajami i ich miastami"""
    hierarchy = {}
    for country in sorted(df['ArrivalCountry'].unique()):
        cities = sorted(df[df['ArrivalCountry'] == country]['Destination'].unique())
        hierarchy[country] = cities
    return hierarchy

# Załaduj dane z kluczem cache na dzisiejszą datę
try:
    with st.spinner('Ładowanie danych lotów...'):
        df_all_flights = load_data(get_cache_key())
        df_ai_deals = load_ai_deals(get_cache_key())
        df_exotic_flights = load_exotic_flights(get_cache_key())
    

    # Logo w sidebar
    st.sidebar.markdown('<div class="logo-container">', unsafe_allow_html=True)
    #st.sidebar.image("assets/logo.svg", width=250)
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    # Logo w sidebar
    st.sidebar.markdown("---")
    
    # Wybór raportu w sidebar - styl przycisków
    st.sidebar.markdown("### Wybierz raport")
    
    # Inicjalizuj session state dla wybranego raportu jeśli nie istnieje
    if 'selected_report' not in st.session_state:
        st.session_state.selected_report = "wszystkie"
    
    # Przycisk Wszystkie Loty
    if st.sidebar.button(
        "📊 Wszystkie Loty", 
        use_container_width=True, 
        type="primary" if st.session_state.selected_report == "wszystkie" else "secondary",
        key="btn_wszystkie"
    ):
        st.session_state.selected_report = "wszystkie"
        st.rerun()
    
    # Przycisk Oferty AI
    if st.sidebar.button(
        "🧠 Oferty AI", 
        use_container_width=True,
        type="primary" if st.session_state.selected_report == "ai" else "secondary",
        key="btn_ai"
    ):
        st.session_state.selected_report = "ai"
        st.rerun()
    
    # Przycisk Loty Egzotyczne
    if st.sidebar.button(
        "🌴 Egzotyka", 
        use_container_width=True,
        type="primary" if st.session_state.selected_report == "exotic" else "secondary",
        key="btn_exotic"
    ):
        st.session_state.selected_report = "exotic"
        st.rerun()
    
    # Ustaw odpowiedni dataset i flagę na podstawie session state
    if st.session_state.selected_report == "wszystkie":
        df = df_all_flights
        show_ai_columns = False
    elif st.session_state.selected_report == "ai":
        df = df_ai_deals
        show_ai_columns = True
    else:  # exotic
        df = df_exotic_flights
        show_ai_columns = False
    
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filtry")
    
    # Filtr miasta wylotu
    origin_cities = sorted(df['Outbound From'].unique())
    selected_origins = st.sidebar.multiselect(
        "Miasto wylotu",
        options=origin_cities,
        default=None,
        help="Wybierz jedno lub więcej miast wylotu"
    )
    
    # Przełącznik powrotu do tego samego miasta
    same_city_return = st.sidebar.toggle(
        "Powrót do tego samego miasta",
        value=False,
        help="Pokaż tylko loty z powrotem do miasta wylotu"
    )
    
    # Filtr miasta powrotu (widoczny tylko gdy przełącznik jest wyłączony)
    selected_return_cities = []
    if not same_city_return:
        return_cities = sorted(df['Inbound To'].unique())
        selected_return_cities = st.sidebar.multiselect(
            "Miasto powrotu",
            options=return_cities,
            default=None,
            help="Wybierz jedno lub więcej miast powrotu"
        )
    
    # Hierarchiczny filtr kraj/miasto
    st.sidebar.subheader("🌍 Destynacja")
    
    destination_hierarchy = create_destination_hierarchy(df)
    
    # Wybór krajów z ikoną
    all_countries = [f"🌍 {country}" for country in sorted(destination_hierarchy.keys())]
    selected_countries_display = st.sidebar.multiselect(
        "Kraj",
        options=all_countries,
        default=None,
        help="Wybierz kraje - filtr miast pokaże tylko miasta z wybranych krajów"
    )
    
    # Usuń ikony z wybranych krajów aby uzyskać rzeczywiste nazwy
    selected_countries = [country.replace("🌍 ", "") for country in selected_countries_display]
    
    # Zbierz miasta z wybranych krajów lub wszystkie miasta jeśli nie wybrano krajów
    if selected_countries:
        available_cities = []
        for country in selected_countries:
            available_cities.extend(destination_hierarchy[country])
        available_cities = sorted(set(available_cities))
    else:
        available_cities = sorted(df['Destination'].unique())
    
    # Dodaj ikony do miast
    available_cities_display = [f"📍 {city}" for city in available_cities]
    
    selected_cities_display = st.sidebar.multiselect(
        "Miasto",
        options=available_cities_display,
        default=None,
        help="Wybierz konkretne miasta (opcjonalne - jeśli puste, uwzględnione będą wszystkie miasta z wybranych krajów)"
    )
    
    # Usuń ikony z wybranych miast
    selected_cities = [city.replace("📍 ", "") for city in selected_cities_display]
    
    # Połącz wybrane kraje i miasta
    final_destinations = set()
    if selected_countries and not selected_cities:
        # Jeśli wybrano tylko kraje, dodaj wszystkie miasta z tych krajów
        for country in selected_countries:
            final_destinations.update(destination_hierarchy[country])
    elif selected_cities:
        # Jeśli wybrano miasta, użyj tylko tych miast
        final_destinations.update(selected_cities)
    elif not selected_countries and not selected_cities:
        # Jeśli nic nie wybrano, nie filtruj
        final_destinations = set()
    
    # Filtry zakresu dat
    st.sidebar.subheader("📅 Zakres dat")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_departure = st.date_input(
            "Wylot od",
            value=df['Departure Date'].min().date(),
            min_value=df['Departure Date'].min().date(),
            max_value=df['Departure Date'].max().date()
        )
    with col2:
        max_departure = st.date_input(
            "Powrót do",
            value=df['Return Date'].max().date(),
            min_value=df['Return Date'].min().date(),
            max_value=df['Return Date'].max().date()
        )
    
    # Filtry dni tygodnia
    #st.sidebar.subheader("📆 Dzień Wylotu / Powrotu")
    days_of_week = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']
    
    selected_departure_days = st.sidebar.multiselect(
        "Dzień wylotu",
        options=days_of_week,
        default=None
    )
    
    selected_return_days = st.sidebar.multiselect(
        "Dzień powrotu",
        options=days_of_week,
        default=None
    )

    # Filtr czasu trwania podróży
    #st.sidebar.subheader("⏱️ Długość Wyjazdu")
    min_duration = int(df['Trip Duration (Days)'].min())
    max_duration = int(df['Trip Duration (Days)'].max())
    
    # Dodaj margines dla lepszego wyświetlania
    st.sidebar.markdown('<div style="padding-right: 10px;">', unsafe_allow_html=True)
    duration_range = st.sidebar.slider(
        "Długość Wyjazdu (dni)",
        min_value=min_duration,
        max_value=max_duration,
        value=(min_duration, max_duration)
    )
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Filtr ceny (bez dziesiętnych)
    #st.sidebar.subheader("💰 Zakres cen")
    min_price = int(df['Total Price'].min())
    max_price = int(df['Total Price'].max())
    
    # Dodaj margines dla lepszego wyświetlania
    st.sidebar.markdown('<div style="padding-right: 10px;">', unsafe_allow_html=True)
    price_range = st.sidebar.slider(
        "Cena lotu (zł)",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        step=10
    )
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Filtry specyficzne dla AI
    if show_ai_columns:
        st.sidebar.subheader("🧠 Filtry AI")
        
        # Filtr AI Score
        min_ai_score = float(df['z_score'].min())
        max_ai_score = float(df['z_score'].max())
        
        st.sidebar.markdown('<div style="padding-right: 10px;">', unsafe_allow_html=True)
        ai_score_range = st.sidebar.slider(
            "AI Score",
            min_value=min_ai_score,
            max_value=max_ai_score,
            value=(min_ai_score, max_ai_score),
            step=0.1
        )
        st.sidebar.markdown('</div>', unsafe_allow_html=True)
        
        # Filtr zmiany ceny
        min_price_change = float(df['price_change_percent'].min())
        max_price_change = float(df['price_change_percent'].max())
        
        st.sidebar.markdown('<div style="padding-right: 10px;">', unsafe_allow_html=True)
        price_change_range = st.sidebar.slider(
            "Zmiana ceny (%)",
            min_value=min_price_change,
            max_value=max_price_change,
            value=(min_price_change, max_price_change),
            step=1.0
        )
        st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    
    # Zastosuj filtry automatycznie
    #st.sidebar.markdown("---")
    # --- After your logo and separator ---

    
    # Zastosuj filtry
    filtered_df = df.copy()
    
    # Filtr powrotu do tego samego miasta
    if same_city_return:
        filtered_df = filtered_df[filtered_df['Outbound From'] == filtered_df['Inbound To']]
    
    if selected_origins:
        filtered_df = filtered_df[filtered_df['Outbound From'].isin(selected_origins)]
    
    # Filtr miasta powrotu (tylko gdy same_city_return jest wyłączony)
    if not same_city_return and selected_return_cities:
        filtered_df = filtered_df[filtered_df['Inbound To'].isin(selected_return_cities)]
    
    if final_destinations:
        filtered_df = filtered_df[filtered_df['Destination'].isin(final_destinations)]
    
    # Filtry dat
    filtered_df = filtered_df[
        (filtered_df['Departure Date'].dt.date >= min_departure) &
        (filtered_df['Departure Date'].dt.date <= max_departure)
    ]
    
    # Filtr czasu trwania
    filtered_df = filtered_df[
        (filtered_df['Trip Duration (Days)'] >= duration_range[0]) &
        (filtered_df['Trip Duration (Days)'] <= duration_range[1])
    ]
    
    # Filtr ceny
    filtered_df = filtered_df[
        (filtered_df['Total Price'] >= price_range[0]) &
        (filtered_df['Total Price'] <= price_range[1])
    ]
    
    # Filtry AI
    if show_ai_columns:
        filtered_df = filtered_df[
            (filtered_df['z_score'] >= ai_score_range[0]) &
            (filtered_df['z_score'] <= ai_score_range[1])
        ]
        filtered_df = filtered_df[
            (filtered_df['price_change_percent'] >= price_change_range[0]) &
            (filtered_df['price_change_percent'] <= price_change_range[1])
        ]
    
    # Filtry dni tygodnia
    if selected_departure_days:
        filtered_df = filtered_df[filtered_df['Departure Day'].isin(selected_departure_days)]
    
    if selected_return_days:
        filtered_df = filtered_df[filtered_df['Return Day'].isin(selected_return_days)]
    
    # Store total count
    total_results = len(filtered_df)
    
    # Wyświetl liczbę wyników
    if total_results > 1000:
        st.markdown(f"### 🎫 Znaleziono {total_results} okazji")
        st.info("💡 Liczba widocznych ofert ograniczona do 1000 wyników")
    else:
        st.markdown(f"### 🎫 Znaleziono {total_results} okazji")
    
    if len(filtered_df) > 0:
        # Opcje sortowania
        col1, col2 = st.columns([3, 1])
        with col1:
            sort_options = {
                'Cena całkowita': 'Total Price',
                'Data wylotu': 'Departure Date',
                'Liczba Dni': 'Trip Duration (Days)',
                'Miejsce docelowe': 'Destination'
            }
            
            # Dodaj opcje sortowania AI jeśli dostępne
            if show_ai_columns:
                sort_options['AI Score'] = 'z_score'
                sort_options['Zmiana ceny (24h)'] = 'price_change_percent'
            
            sort_by_pl = st.selectbox(
                "Sortuj według",
                options=list(sort_options.keys()),
                index=0
            )
            sort_by = sort_options[sort_by_pl]
        with col2:
            sort_order = st.radio("Kolejność", ["Rosnąco", "Malejąco"], horizontal=True)
        
        ascending = sort_order == "Rosnąco"
        filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)
        
        # LIMIT TO 1000 ROWS FOR DISPLAY
        display_limited_df = filtered_df.head(1000)
        
        # Przygotuj dataframe do wyświetlenia
        display_df = display_limited_df.copy()
        
        # Formatuj daty - bez dni tygodnia dla AI tab (oszczędność miejsca)
        if show_ai_columns:
            display_df['Wylot'] = display_df['Departure Date'].dt.strftime('%Y-%m-%d')
            display_df['Powrót'] = display_df['Return Date'].dt.strftime('%Y-%m-%d')
        else:
            display_df['Wylot'] = display_df.apply(
                lambda row: f"{row['Departure Date'].strftime('%Y-%m-%d')} ({row['Departure Day']})", 
                axis=1
            )
            display_df['Powrót'] = display_df.apply(
                lambda row: f"{row['Return Date'].strftime('%Y-%m-%d')} ({row['Return Day']})", 
                axis=1
            )
        
        # Formatuj ceny (usuń .00 dla całkowitych)
        def format_price(x):
            if x == int(x):
                return f"{int(x)} zł"
            else:
                return f"{x:.2f} zł"
        
        display_df['Cena'] = display_df['Total Price'].apply(format_price)
        
        # Przygotuj kolumny do wyświetlenia
        display_df['Z'] = display_df['Outbound From']
        display_df['Do'] = display_df['Destination']
        display_df['Kraj'] = display_df['ArrivalCountry']
        display_df['Powrót do'] = display_df['Inbound To']
        display_df['Link'] = display_df['Round_Trip_Link']
        
        # Dodaj kolumny AI jeśli to raport Oferty AI
        if show_ai_columns:
            display_df['AI Score'] = display_df['z_score'].apply(lambda x: f"{x:.2f}")
            display_df['Δ Cena'] = display_df['price_change_percent'].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A"
            )
        
        # Wybierz i uporządkuj kolumny do wyświetlenia
        if show_ai_columns:
            display_columns = [
                'Z', 'Do', 'Powrót do', 'Kraj',
                'Wylot', 'Powrót',
                'Cena', 'AI Score', 'Δ Cena',
                'Link'
            ]
        else:
            display_columns = [
                'Z', 'Do', 'Powrót do', 'Kraj',
                'Wylot', 'Powrót',
                'Cena',
                'Link'
            ]
        
        # Wyświetl tabelę z poprawną konfiguracją linków i autofitem kolumn
        column_config = {
            "Link": st.column_config.LinkColumn(
                "Rezerwuj",
                display_text="Kup bilet"
            ),
            "Z": st.column_config.TextColumn("Z"),
            "Do": st.column_config.TextColumn("Do"),
            "Powrót do": st.column_config.TextColumn("Powrót do"),
            "Kraj": st.column_config.TextColumn("Kraj"),
            "Wylot": st.column_config.TextColumn("Wylot"),
            "Powrót": st.column_config.TextColumn("Powrót"),
            "Cena": st.column_config.TextColumn("Cena"),
        }
        
        # Dodaj konfigurację kolumn AI jeśli potrzebna
        if show_ai_columns:
            column_config["AI Score"] = st.column_config.TextColumn(
                "AI Score",
                help="Ocena AI: im wyższa wartość, tym lepsza okazja"
            )
            column_config["Δ Cena"] = st.column_config.TextColumn(
                "Δ Cena",
                help="Zmiana ceny w ciągu ostatnich 24 godzin (%)"
            )
        
        st.dataframe(
            display_df[display_columns],
            use_container_width=True,
            height=600,
            column_config=column_config,
            hide_index=True
        )
        
        # Statystyki podsumowujące (based on ALL filtered results, not just displayed 1000)
        st.markdown("---")
        st.markdown("### 📊 Statystyki twojego wyszukiwania")
        
        if show_ai_columns:
            col1, col2, col3, col4, col5, col6 = st.columns(6)
        else:
            col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_price = filtered_df['Total Price'].astype(float).mean()
            if avg_price == int(avg_price):
                st.metric("Średnia cena", f"{int(avg_price)} zł")
            else:
                st.metric("Średnia cena", f"{avg_price:.2f} zł")
        
        with col2:
            min_price_val = filtered_df['Total Price'].astype(float).min()
            if min_price_val == int(min_price_val):
                st.metric("Najniższa cena", f"{int(min_price_val)} zł")
            else:
                st.metric("Najniższa cena", f"{min_price_val:.2f} zł")
        
        with col3:
            avg_duration = filtered_df['Trip Duration (Days)'].mean()
            st.metric("Średni czas", f"{avg_duration:.1f} dni")
        
        with col4:
            destinations_count = filtered_df['Destination'].nunique()
            st.metric("Liczba destynacji", destinations_count)
        
        if show_ai_columns:
            with col5:
                avg_ai_score = filtered_df['z_score'].mean()
                st.metric("Średni AI Score", f"{avg_ai_score:.2f}")
            
            with col6:
                avg_price_change = filtered_df['price_change_percent'].mean()
                st.metric("Średnia zmiana ceny", f"{avg_price_change:+.1f}%")
        
    else:
        st.warning("Brak lotów spełniających wybrane kryteria. Spróbuj dostosować filtry.")
        
except Exception as e:
    st.error(f"Błąd podczas ładowania danych: {str(e)}")
    st.info("Sprawdź URL pliku CSV i upewnij się, że jest dostępny.")
