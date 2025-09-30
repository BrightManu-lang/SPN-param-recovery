# Standard Packages
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Spatial Handling
import geopandas as gpd
from shapely.geometry import LineString, box, Point
from math import radians, sin, cos, sqrt, atan2
from scipy.spatial.distance import euclidean
from shapely.ops import nearest_points

import math
import glob

import warnings
import os
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import itertools

warnings.filterwarnings(category=FutureWarning, action='ignore')
warnings.filterwarnings(category=DeprecationWarning, action='ignore')
warnings.filterwarnings(category=UserWarning, action='ignore')

class Polygon:
    @staticmethod
    def polygoninitialization(exclude_non_mainland=True, state_init=None, county_name=None):
        # Load US county shapefile
        shapefile_path = r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/shapefiles/cb_2023_us_county_500k.shp"
        gdf = gpd.read_file(shapefile_path)
        gdf = gdf.to_crs(epsg=4326)

        # Filter for only mainland US states if specified
        if exclude_non_mainland:
            gdf = gdf[(pd.to_numeric(gdf['STATEFP']) < 60) & (pd.to_numeric(gdf['STATEFP']) != 2) & (pd.to_numeric(gdf['STATEFP']) != 15)]

        # Filter by specific state by initial
        if state_init:
            gdf = gdf[gdf['STUSPS'] == str(state_init)]

        # Filter by county
        if county_name:
            gdf = gdf[gdf['NAME'].str.lower() == county_name.lower()]

        gdf['STATEFP'] = gdf['STATEFP'].astype(int)
        gdf = gdf.drop(columns=['LSAD', 'ALAND', 'AWATER'])
        return gdf.reset_index(drop=True)


class Grid:
    @staticmethod
    def create_grid(df, grid_size, mode="default"):
        grid_creator = GridCreator(df, grid_size=grid_size, mode=mode)
        return grid_creator.create_grid()


class GridCreator:
    def __init__(self, gdf, grid_size, overlap=True, crs="EPSG:4326", mode="default"):
        self.gdf = gdf
        self.grid_size = grid_size
        self.overlap = overlap
        self.crs = crs
        self.mode = mode  # New mode parameter to differentiate between methods

    def create_grid(self):
        lon_min, lat_min, lon_max, lat_max = self.gdf.total_bounds

        if self.mode == "square":
            # Ensuring grid_size x grid_size grid when grid_size = 2 → 2x2 grid
            cell_width = (lon_max - lon_min) / self.grid_size
            cell_height = (lat_max - lat_min) / self.grid_size

            grid_cells = [
                box(lon0, lat0, lon0 + cell_width, lat0 + cell_height)
                for lat0 in np.linspace(lat_min, lat_max - cell_height, self.grid_size)[::-1]
                for lon0 in np.linspace(lon_min, lon_max - cell_width, self.grid_size)
            ]

        elif self.mode == "horizontal":
            # split into `grid_size` horizontal strips
            cell_height = (lat_max - lat_min) / self.grid_size
            grid_cells = [
                box(lon_min, lat0, lon_max, lat0 + cell_height)
                for lat0 in np.linspace(lat_min, lat_max - cell_height, self.grid_size)[::-1]
            ]

        else:
            # Default behavior: creates exactly "grid_size" number of cells
            step_size = (lon_max - lon_min) / self.grid_size
            grid_cells = [
                box(lon0, lat_min, lon0 + step_size, lat_max)
                for lon0 in np.linspace(lon_min, lon_max - step_size, self.grid_size)
            ]

        cells = gpd.GeoDataFrame(grid_cells, columns=['geometry'], crs=self.crs)
        cells['ID'] = range(1, len(cells) + 1)

        # filter grid cells to only those overlapping the area of interest
        if self.overlap:
            cells = cells.sjoin(self.gdf, how='inner').drop_duplicates('geometry')
            cells['ID'] = range(1, len(cells) + 1)

        return cells


class Adjacency_Polygon:
    @classmethod
    def calculate_adjacency_matrix(cls, grid):
        n = len(grid)
        adj_matrix = np.zeros((n, n), dtype=int)

        # Moore neighborhood (grid neighbors that share sides/corners)
        for i in range(n):
            for j in range(i + 1, n):
                if grid.iloc[i].geometry.touches(grid.iloc[j].geometry):
                    adj_matrix[i, j] = 1
                    adj_matrix[j, i] = 1

        return pd.DataFrame(adj_matrix, index=range(1, n + 1), columns=range(1, n + 1))


grid_size = 2

# Load all mainland US
# us_polygon = Polygon.polygoninitialization(exclude_non_mainland=True)

# Create a grid for the US
# grid_us_default = Grid.create_grid(us_polygon, grid_size, mode="default")
# grid_us_2x2 = Grid.create_grid(us_polygon, grid_size, mode="square")

# Load a specific state (e.g., California with FIPS = "06")
county_polygon = Polygon.polygoninitialization(exclude_non_mainland=True, state_init="AZ", county_name='Maricopa')

# Create a grid for Arizona
grid1 = Grid.create_grid(county_polygon, grid_size, mode="horizontal")
# grid_ca_2x2 = Grid.create_grid(county_polygon, grid_size, mode="square")

# Adjacency matrix for a selected grid
adj_matrix = Adjacency_Polygon.calculate_adjacency_matrix(grid1)
# adj_matrix = Adjacency_Polygon.calculate_adjacency_matrix(grid_ca_2x2)

# Display selected grid
# grid_ca_2x2

# grid1

maricopa_cty_polygon = Polygon.polygoninitialization(exclude_non_mainland=True, state_init="AZ", county_name="Maricopa")

df = pd.read_excel(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/data/ALERT_sensors_all_by_name.xlsx")
stations_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude_DD, df.Latitude_DD), crs="EPSG:4326")
stations_gdf = stations_gdf.drop(columns=['Dev._Type', 'Installed', 'Device_ID', 'Station_Location'])

keep_df = pd.read_excel(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/data/Weather_Stations_names.xlsx")
keep_df["BaseName"] = (keep_df["Station"].str.split(",", n=1).str[0].str.strip())

filt_stations_gdf = stations_gdf[stations_gdf["Station_Name"].isin(keep_df["BaseName"])].copy()
filt_stations_gdf = filt_stations_gdf.drop_duplicates()
filt_stations_gdf = filt_stations_gdf.reset_index(drop=True)

maricopa_stations = gpd.sjoin(filt_stations_gdf, maricopa_cty_polygon, how="left")
maricopa_stations = maricopa_stations.drop(columns=['index_right'])

maricopa_stations1 = gpd.sjoin(filt_stations_gdf, maricopa_cty_polygon, how="inner", predicate="within")
maricopa_stations1 = maricopa_stations1.reset_index(drop=True)

env_data = pd.read_csv(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/data/new_Maricopa_WS_daily_data1.csv")
env_data['Station_Name'] = (env_data["Station_name"].str.split(",", n=1).str[0].str.strip())
env_data = env_data.drop(columns=['Station_name', 'Day', 'Date'])
# env_data['RH_avg'] = (env_data['RH_max'] + env_data['RH_min']) / 2 
# env_data
# apply a 7-day centered moving average to your RH_min and RH_max
env_data['RH_min_smooth'] = (env_data['RH_min'].rolling(window=7, center=True, min_periods=1).mean())
env_data['RH_max_smooth'] = (env_data['RH_max'].rolling(window=7, center=True, min_periods=1).mean())

# smooth Tmin and Tmax over a 7-day window
env_data['Tmin_smooth'] = (env_data['Temp_min_C'].rolling(window=7, center=True, min_periods=1).mean())
env_data['Tmax_smooth'] = (env_data['Temp_max_C'].rolling(window=7, center=True, min_periods=1).mean())

stations_env = maricopa_stations1.merge(env_data, on="Station_Name", how="inner")
stations_env = stations_env.drop(columns=['index_right', 'COUNTYNS', 'GEOIDFQ', 'NAMELSAD', 'STATE_NAME'])
# stations_env

pts_in_grid = gpd.sjoin(stations_env, grid1[['ID','geometry']], how='inner', predicate='within')
cell_means = (pts_in_grid.groupby(['ID', 'Day_cont'])[['Temp_max','Temp_avg','Temp_min','RH_max','RH_min', 'RH_min_smooth', 'RH_max_smooth', 'Temp_max_C',
                'Temp_avg_C', 'Temp_min_C', 'Tmin_smooth', 'Tmax_smooth']].mean().reset_index())
grid_daily = grid1.merge(cell_means, on='ID', how='right')
grid_daily = grid_daily.drop(columns=['index_right', 'COUNTYNS', 'GEOIDFQ', 'NAMELSAD', 'STATE_NAME'])

MODEL_PATH = Path(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/SIRS_Mosq_2grid_new_new.andl")
OUTPUT_DIR = Path(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/Sim_no_centering_new_funct")
SPIKE_EXE  = Path(r"/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/spike")

# number of underlying constant samples
N_samples = 5000

# Basis functions
def briere(T, a, Tmin, Tmax):
    if T <= Tmin or T >= Tmax:
        return 0.0
    return a * T * (T - Tmin) * math.sqrt(Tmax - T)

def logistic(RH, k, RHopt):
    return 1.0 / (1.0 + math.exp(-k * (RH - RHopt)))

def quad_surv(T, T0, Tm, c):
    return np.clip(c * (T - T0)*(T - Tm), 0.0, 1.0)

def L_eff_multi(RH_min, RH_max, k, RHopt, n):
    """
    Approximate the 24h mean of logistic(RH) by sampling n points
    along a half-cosine diurnal curve between RH_min and RH_max.
    """
    ts = np.linspace(0, 1, n)  # fraction of day
    RHs = RH_min + (RH_max - RH_min) * 0.5 * (1 - np.cos(2 * np.pi * ts))
    return np.mean([logistic(rh, k, RHopt) for rh in RHs])

def diffusion_coeff_piecewise_diurnal(T, RH_min, RH_max, Tmin_mig, Tmax_mig, k, RHopt, n=6):
    if (T <= Tmin_mig) or (T >= Tmax_mig):
        return 0.0
    return L_eff_multi(RH_min, RH_max, k, RHopt, n=n)

def hourly_avg_briere(Tmean, Tmin_obs, Tmax_obs, a, Tmin, Tmax):
    DTR = Tmax_obs - Tmin_obs
    hours = np.arange(24)
    T_hr = Tmean + (DTR / 2) * np.sin((2 * np.pi / 24) * hours - np.pi/2)
    vals = []
    for Th in T_hr:
        if Th <= Tmin or Th >= Tmax:
            vals.append(0.0)
        else:
            vals.append(a * Th * (Th - Tmin) * math.sqrt(Tmax - Th))
    return np.mean(vals)

def haversine_distance(coord1, coord2):
    R = 3959.0  # Earth radius in miles
    lat1, lon1 = radians(coord1[0]), radians(coord1[1])
    lat2, lon2 = radians(coord2[0]), radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def compute_centroid_dist_matrix(grid):
    P = len(grid)
    D_cent = np.zeros((P, P))
    centroids = [(pt.y, pt.x) for pt in grid.geometry.centroid]
    for i in range(P):
        for j in range(i + 1, P):
            d = haversine_distance(centroids[i], centroids[j])
            D_cent[i, j] = d
            D_cent[j, i] = d
    return D_cent

def compute_boundary_dist_matrix(grid):
    P = len(grid)
    D_bound = np.zeros((P, P))
    for i in range(P):
        for j in range(i + 1, P):
            poly_i = grid.geometry.iloc[i]
            poly_j = grid.geometry.iloc[j]
            p_i, p_j = nearest_points(poly_i, poly_j)
            coord_i = (p_i.y, p_i.x)
            coord_j = (p_j.y, p_j.x)
            d = haversine_distance(coord_i, coord_j)
            D_bound[i, j] = d
            D_bound[j, i] = d
    return D_bound

def env_scaler(row, params):
    Tmean    = row['Temp_avg_C']
    Tmin_obs = row['Tmin_smooth']
    Tmax_obs = row['Tmax_smooth']
    RH_min = row['RH_min_smooth']
    RH_max = row['RH_max_smooth']
    # RH       = row['RH_avg']

    # Transmission Brière
    briere_avg = hourly_avg_briere(
        Tmean, Tmin_obs, Tmax_obs,
        params['a'], params['Tmin'], params['Tmax']
    )
    B_bar = briere_avg

    # Diffusion coefficient (temperature gate + humidity)
    D_mig = diffusion_coeff_piecewise_diurnal(
        Tmean, RH_min, RH_max,
        params['Tmin_mig'], params['Tmax_mig'],
        params['k'], params['RHopt'], n=6
    )

    # Humidity scaling
    L_rh   = L_eff_multi(RH_min, RH_max, params['k'], params['RHopt'], n=6)

    # Quad mortality
    m_daily = quad_surv(Tmean, params['T0'], params['Tm'], params['c'])
    mort_day = m_daily

    return B_bar, D_mig, L_rh, mort_day

def bound_to_range(x, lo, hi):
    return lo + (hi - lo) / (1.0 + np.exp(-x))

def compute_feature_table(env_df, params):
    """Return only raw environmental covariates for centering."""
    recs = []
    for _, row in env_df.iterrows():
        day   = int(row['Day_cont'])
        patch = int(row['ID'])
        B_bar, D_mig, L_rh, mort_day = env_scaler(row, params)
        recs.append({
            'Day': day, 'Patch': patch,
            'B_bar': B_bar, 'D_mig': D_mig, 'L_rh': L_rh, 'mort_M': mort_day
        })
    return pd.DataFrame.from_records(recs)

def compute_within_patch_rates(env_df, params):
    records = []
    for _, row in env_df.iterrows():
        day   = int(row['Day_cont'])
        patch = int(row['ID'])
        B_bar, D_mig, L_rh, mort_day = env_scaler(row, params)

        # Within-patch β_HM:
        beta_MH_ii = (
            params['lambda0_MH']
            + params['lambda1_MH'] * B_bar
            + params['lambda2_MH'] * L_rh
            # + params['lambda3_MH'] * B_bar * L_rh
        )
        # Within-patch β_MH:
        beta_HM_ii = (
            params['gamma0_HM']
            + params['gamma1_HM'] * B_bar
            + params['gamma2_HM'] * L_rh
            # + params['gamma3_HM'] * B_bar * L_rh
        )
        # Mosquito mortality μ_M^(i,i):
        mu_M_ii = (
            params['p0_mortality']
            + params['p1_mortality'] * mort_day
            + params['p2_mortality'] * L_rh
        )

        rec = {
            'Day':     day,
            'Patch':   patch,
            'B_bar':   B_bar,
            'D_mig': D_mig,
            'L_rh':    L_rh,
            'mort_M':  mort_day,
            'beta_MH': beta_MH_ii,
            'beta_HM': beta_HM_ii,
            'mu_M':    mu_M_ii
        }
        records.append(rec)

    return pd.DataFrame.from_records(records,
                                     columns=[
                                         'Day','Patch','B_bar', 'D_mig', 'L_rh','mort_M',
                                         'beta_MH','beta_HM','mu_M'
                                     ])

def compute_theta_alpha(i, j, D_human, D_mosq, c_vals):
    d_h = D_human[i-1, j-1]
    theta_S = 1.0 / (c_vals['S'] + d_h**2)
    theta_I = 1.0 / (c_vals['I'] + d_h**2)
    theta_R = 1.0 / (c_vals['R'] + d_h**2)

    d_m = D_mosq[i-1, j-1]
    if d_m > 3.0:
        alpha_S_raw = 0.0
        alpha_I_raw = 0.0
    else:
        alpha_S_raw = 1.0 / (c_vals['alpha_S'] + d_m**2)
        alpha_I_raw = 1.0 / (c_vals['alpha_I'] + d_m**2)

    return theta_S, theta_I, theta_R, alpha_S_raw, alpha_I_raw

def compute_between_patch_rates_asymmetric(local_rates_df, D_human, D_mosq, c_vals, params):
    # env lookup
    env = {(int(r['Day']), int(r['Patch'])): r for _, r in local_rates_df.iterrows()}
    P = D_human.shape[0]
    rows = []

    for (day, i), ei in env.items():
        Bi, Li = float(ei['B_bar']), float(ei['L_rh'])
        # Di_mig = float(ei['D_mig'])
        for j in range(1, P+1):
            if j == i: 
                continue
            ej = env[(day, j)]
            Dj_mig = float(ej['D_mig'])

            # Asymmetric rules
            beta_MH_ij = (params['delta0_MH']
                          + params['delta1_MH']*Bi
                          + params['delta2_MH']*Li)
                        #   + params['delta3_MH']*Bi*Li)   # uses destination i
            beta_HM_ij = (params['eta0_HM']
                          + params['eta1_HM']*Bi
                          + params['eta2_HM']*Li)
                        #   + params['eta3_HM']*Bi*Li)     # uses destination i

            _, _, _, d_MS, d_MI = compute_theta_alpha(
                i, j, D_human, D_mosq, c_vals
            )
            alpha_SM = (d_MS * params['iota1'] * Dj_mig)   # source j
            alpha_IM = (d_MI * params['iota2'] * Dj_mig)   # source j

            rows.append({'Day': day, 'From': i, 'To': j,
                         'beta_MH': beta_MH_ij, 'beta_HM': beta_HM_ij,
                         'alpha_SM': alpha_SM, 'alpha_IM': alpha_IM})
    return pd.DataFrame(rows, columns=['Day','From','To','beta_MH','beta_HM','alpha_SM','alpha_IM'])

# write spc and run spike
def write_spc_file(spc_path: Path, model_file: Path, output_dir: Path, rates_df, sample_id: int):
    """Write an SPC that runs all days stepwise with onStep updates."""
    mf = model_file
    od_posix = output_dir.as_posix()

    with open(spc_path, 'w', encoding='utf-8') as f:
        f.write('/**\n')
        f.write(' * Configuration of Vector Model\n')
        f.write(' */\n\n')

        # import block
        f.write('import: {\n')
        f.write(f'    from: "{mf}";\n')
        f.write('}\n\n')

        # configuration block
        f.write('configuration: {\n\n')

        # model constants
        f.write('  model: {\n')
        f.write('    constants: {\n')
        f.write('      parameter: {\n')
        f.write('      }\n')
        f.write('    }\n')
        f.write('    places: {\n')
        f.write('       // SH1: [[1000, 2000]];\n')
        f.write('    }\n')
        f.write('  }\n\n')

        # simulation 
        # T = len(rates_df)
        f.write('  simulation: {\n')
        f.write('    name: "SIRIS";\n')
        f.write('    type: [[\n')
        f.write('      stochastic: {\n')
        f.write('        solver: direct: {\n')
        f.write('           threads: 3;\n')
        f.write('           runs: 2;\n')
        f.write('        }\n')
        f.write('      }\n')
        f.write('    ]];\n')
        f.write('    interval: 0:365:365;\n\n')

        # Stepwise block
        f.write('    onStep: enabled: {\n')
        f.write('       do:{\n')
        for _, row in rates_df.iterrows():
            d = int(row['Day'])
            f.write(f'      if (simulation.step == {d}) {{ \n')
            for col in rates_df.columns.drop('Day'):
                v = row[col]
                f.write(f'        constant.{col} = {v:.6e};\n')
            f.write('      }\n')
        f.write('    }\n')
        f.write('  }\n\n')

        # export block
        filename = f"sample_{sample_id:02d}_stepwise"
        f.write('    export: {\n')
        f.write('      places: []; // all places\n')
        f.write('      transitions: []; // all transitions\n')
        f.write('      observers: [];\n')
        f.write('      csv: {\n')
        f.write('        sep: ","; // Separator\n')
        f.write(f'        file: "{od_posix}/{filename}"\n')
        f.write('           << ".csv";\n')
        f.write('      }\n')
        f.write('    }\n')
        f.write('  }\n')
        f.write('}\n\n')

        # log block
        f.write('log: {\n')
        f.write('  sim.varExa: configuration.simulation.type;\n')
        f.write('}')

def run_spike(spike_executable: Path, spc_path: Path, sample_id: int) -> None:
    '''Write SPC, invoke Spike, then delete the file.'''
    if sample_id is not None:
        port = 7777 + int(sample_id)
        cmd = f'"{spike_executable}" exe -f="{spc_path}" -port={port}'
    else:
        cmd = f'"{spike_executable}" exe -f="{spc_path}"'
    print(f"[INFO] Running command: {cmd}")
    try:
        res = subprocess.run(cmd, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("[INFO] Simulation completed successfully.")
        if res.stdout:
            print(res.stdout.decode(errors='ignore'))
        if res.stderr:
            print("[WARN] ", res.stderr.decode(errors='ignore'))
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Simulation failed (exit code {e.returncode}):")
        print(e.stderr.decode(errors='ignore'))
    finally:
        spc_path.unlink(missing_ok=True)
        print(f"[INFO] Removed temporary SPC file: {spc_path}")

# simulate samples in parallel
def simulate_sample(s, env_df, P, days, D_human, D_mosq, c_vals, rate_col_names):
    np.random.seed(42 + s)  # reproducible & different per sample

    print(f"\n=== Generating Sample {s} of {N_samples-1} ===")

    # Ross–Macdonald range (per bite per day)
    beta_min_MH, beta_max_MH = 0.01, 0.80   # mosquito → human
    beta_min_HM, beta_max_HM = 0.072, 0.64  # human → mosquito
    Delta_MH = beta_max_MH - beta_min_MH
    Delta_HM = beta_max_HM - beta_min_HM

    # Ross–Macdonald mosquito mortality (per day)
    mu_min, mu_max = 0.05, 0.33
    Delta_mu = mu_max - mu_min
    
    # Migration rate range from lit
    min_alpha, max_alpha = 0.06, 0.60

    # Within‐patch HM
    lambda0_MH = beta_min_MH
    lambda1_MH = np.random.uniform(0, Delta_MH)
    lambda2_MH = np.random.uniform(0, Delta_MH)
    # lambda3_MH = np.random.uniform(0, Delta_MH)

    # Within‐patch MH
    gamma0_HM = beta_min_HM
    gamma1_HM = np.random.uniform(0, Delta_HM)
    gamma2_HM = np.random.uniform(0, Delta_HM)
    # gamma3_HM = np.random.uniform(0, Delta_HM)

    # Between‐patch HM
    delta0_MH = beta_min_MH
    delta1_MH = np.random.uniform(0, Delta_MH)
    delta2_MH = np.random.uniform(0, Delta_MH)
    # delta3_MH = np.random.uniform(0, Delta_MH)

    # Between‐patch MH
    eta0_HM   = beta_min_HM
    eta1_HM   = np.random.uniform(0, Delta_HM)
    eta2_HM   = np.random.uniform(0, Delta_HM)
    # eta3_HM   = np.random.uniform(0, Delta_HM)

    # Mosquito mortality (global)
    p0_mortality = mu_min
    p1_mortality = np.random.uniform(0, Delta_mu)
    p2_mortality = np.random.uniform(0, Delta_mu)

    # Migration
    iota1 = np.random.uniform(min_alpha, max_alpha)
    iota2 = np.random.uniform(min_alpha, max_alpha)

    const_dict = {
        # within‐patch MH
        "lambda0_MH": lambda0_MH,
        "lambda1_MH": lambda1_MH,
        "lambda2_MH": lambda2_MH,
        # "lambda3_MH": lambda3_MH,

        # within‐patch HM
        "gamma0_HM":  gamma0_HM,
        "gamma1_HM":  gamma1_HM,
        "gamma2_HM":  gamma2_HM,
        # "gamma3_HM":  gamma3_HM,

        # between‐patch MH
        "delta0_MH":  delta0_MH,
        "delta1_MH":  delta1_MH,
        "delta2_MH":  delta2_MH,
        # "delta3_MH":  delta3_MH,

        # between‐patch HM
        "eta0_HM":    eta0_HM,
        "eta1_HM":    eta1_HM,
        "eta2_HM":    eta2_HM,
        # "eta3_HM":    eta3_HM,

        # mosquito mortality
        "p0_mortality": p0_mortality,
        "p1_mortality": p1_mortality,
        "p2_mortality": p2_mortality,

        # Migration
        "iota1": iota1,
        "iota2": iota2
    }

    record = {'sample_id': s}
    record.update(const_dict)

    params_s = {
        'a':      2.71e-4,  'Tmin':   14.67,  'Tmax':   41.0,
        'k':      0.1,      'RHopt':  70.0, 'c': -3.36e-3,
        'T0': 7.68,  'Tm':  38.31,  'Tmin_mig': 10.0, 'Tmax_mig': 35.0,

        'lambda0_MH':   lambda0_MH,
        'lambda1_MH':   lambda1_MH,
        'lambda2_MH':   lambda2_MH,
        # 'lambda3_MH':   lambda3_MH,

        'gamma0_HM':    gamma0_HM,
        'gamma1_HM':    gamma1_HM,
        'gamma2_HM':    gamma2_HM,
        # 'gamma3_HM':    gamma3_HM,

        'delta0_MH':    delta0_MH,
        'delta1_MH':    delta1_MH,
        'delta2_MH':    delta2_MH,
        # 'delta3_MH':    delta3_MH,

        'eta0_HM':      eta0_HM,
        'eta1_HM':      eta1_HM,
        'eta2_HM':      eta2_HM,
        # 'eta3_HM':      eta3_HM,

        'p0_mortality': p0_mortality,
        'p1_mortality': p1_mortality,
        'p2_mortality': p2_mortality,

        'iota1': iota1,
        'iota2': iota2
    }

    # Compute rates
    local_rates_df_s = compute_within_patch_rates(env_df, params_s)
    between_rates_df_s = compute_between_patch_rates_asymmetric(local_rates_df_s, D_human, D_mosq, c_vals, params_s)

    # Build rates_df
    rows = []
    for d in days:
        daily_dict = {'Day': d}
        # within‐patch
        df_loc_d = local_rates_df_s[local_rates_df_s['Day'] == d]
        for i in range(1, P+1):
            row_i = df_loc_d[df_loc_d['Patch'] == i].iloc[0]
            daily_dict[f"betaMH_{i}_{i}"] = row_i['beta_MH']
            daily_dict[f"betaHM_{i}_{i}"] = row_i['beta_HM']
            daily_dict[f"muM_{i}"]        = row_i['mu_M']

        # between‐patch
        df_betw_d = between_rates_df_s[between_rates_df_s['Day'] == d]
        for i in range(1, P+1):
            for j in range(1, P+1):
                if i == j: 
                    continue
                row_ij = df_betw_d[(df_betw_d['From'] == i) & (df_betw_d['To'] == j)].iloc[0]
                daily_dict[f"betaMH_{i}_{j}"]  = row_ij['beta_MH']
                daily_dict[f"betaHM_{i}_{j}"]  = row_ij['beta_HM']
                daily_dict[f"alpha_SM_{i}{j}"] = row_ij['alpha_SM']
                daily_dict[f"alpha_IM_{i}{j}"] = row_ij['alpha_IM']

        rows.append(daily_dict)

    rates_df = pd.DataFrame(rows, columns=rate_col_names)

    # Per-sample output
    sample_folder = OUTPUT_DIR / f"sample_{s:02d}"
    sample_folder.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".spc", delete=False) as tmp:
        spc_file = Path(tmp.name)

    write_spc_file(spc_file, MODEL_PATH, sample_folder, rates_df, sample_id=s)
    run_spike(SPIKE_EXE, spc_file, sample_id=s)

    print(f"✅ Sample {s}: stepwise simulation complete ({len(rates_df)} days)")
    return record


# run main
def main():
    # check output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # prepare and load data
    env_df = grid_daily[grid_daily['Day_cont'] <= 365]
    P      = len(grid1)                     
    days   = sorted(env_df['Day_cont'].unique()) 

    # Pre‐compute distances & c_vals once
    D_human = compute_centroid_dist_matrix(grid1)
    D_mosq  = compute_boundary_dist_matrix(grid1)
    c_vals  = {'S': 10, 'I': 15, 'R': 20, 'alpha_S': 5, 'alpha_I': 2}

    # Build a list of rate‐column names (Day + 14 rate columns when P=2)
    rate_col_names = ['Day']
    for i in range(1, P+1):
        rate_col_names.append(f"betaHM_{i}_{i}")
        rate_col_names.append(f"betaMH_{i}_{i}")
        rate_col_names.append(f"muM_{i}")
    for i in range(1, P+1):
        for j in range(1, P+1):
            if i == j:
                continue
            rate_col_names.append(f"betaHM_{i}_{j}")
            rate_col_names.append(f"betaMH_{i}_{j}")
            rate_col_names.append(f"alpha_SM_{i}{j}")
            rate_col_names.append(f"alpha_IM_{i}{j}")

    # store all constants for each sample s — collected from parallel results
    with ThreadPoolExecutor(max_workers=30) as executor:  # or os.cpu_count()
        constants_records = list(executor.map(
            simulate_sample,
            range(N_samples),
            itertools.repeat(env_df),
            itertools.repeat(P),
            itertools.repeat(days),
            itertools.repeat(D_human),
            itertools.repeat(D_mosq),
            itertools.repeat(c_vals),
            itertools.repeat(rate_col_names),
        ))

    # After all N_samples done, write out constants.csv
    constants_df = pd.DataFrame(constants_records).sort_values('sample_id')
    constants_df.to_csv(OUTPUT_DIR / "constants.csv", index=False)
    print(f"\nAll done! Wrote constants.csv and Spike outputs under:\n  {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()