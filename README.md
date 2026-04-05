# 🚚 Delievery-Route-Optimization
**Multi-Vehicle Sustainable Route Optimization using Heuristic Vehicle Routing Problem (VRP)**
---

## 🔥 Project Overview

Last-mile logistics contributes **over 50% of operational costs** and significantly impacts carbon emissions in urban areas.

**Delivery Route Optimizer** is an AI-powered, sustainable, and priority-aware routing engine that:

- Optimizes routes for multiple vehicles simultaneously.
- Prioritizes **perishable items** and **time-sensitive deliveries**.
- Reduces total distance, fuel usage, and CO₂ emissions.
- Provides a **live interactive map** with vehicle-wise routes.
- Balances delivery loads across multiple vehicles for operational efficiency.

This tool is perfect for logistics startups, e-commerce businesses, or urban delivery services aiming to **save cost, time, and carbon footprint**.

---
## 🎯 Features

<table>
<tr>
<td width="50%">

### 🗺️ Smart Multi-Vehicle Routing
- Hybrid heuristic VRP engine  
- Brute-force (≤8 stops) → optimal  
- Nearest Neighbor + 2-Opt (>8 stops)  
- Cross-cluster optimization [F1]  
- Guaranteed improvement over naive routing  

</td>
<td width="50%">

### 🔵 Constraint-Aware Clustering
- KMeans with priority weighting  
- DBSCAN dynamic tuning [F3]  
- Agglomerative fallback  
- Hybrid Sweep algorithm [F4]  

</td>
</tr>

<tr>
<td width="50%">

### ⚡ Performance Optimization
- Distance matrix caching [F5]  
- Haversine fallback (>30 stops)  
- Geocoding cache [F6]  
- Reduced API usage  

</td>
<td width="50%">

### 🌿 Sustainability Insights
- Fuel consumption tracking  
- CO₂ emission estimation  
- Eco-efficiency score  
- Environmental impact metrics  

</td>
</tr>

<tr>
<td width="50%">

### 🚦 Dynamic Re-Routing
- Traffic delay simulation [F7]  
- 20% delay probability  
- 1.2×–2.0× delay factor  
- Automatic rerouting  

</td>
<td width="50%">

### 📁 CSV Bulk Import
- UTF-8 validation [F8]  
- Duplicate removal  
- Row limit enforcement  
- Clean error handling  

</td>
</tr>

<tr>
<td width="50%">

### 🗺️ Visualization Engine
- Folium interactive maps [F10]  
- Vehicle-wise route layers  
- Heatmap visualization  
- Inefficiency detection  

</td>
<td width="50%">

### 📄 PDF Export
- One-click report generation  
- Route + metrics summary  
- Timestamped outputs  
- Driver-ready sheets  

</td>
</tr>
</table>


## 📊 How It Works

### 📍 1. Geocoding
- Converts delivery addresses into coordinates using **OpenRouteService**
- Falls back to **Nominatim (OpenStreetMap)** for reliability

---

### 📏 2. Distance Matrix
- Computes pairwise distances between all locations  
- Uses **ORS road-network distance API** for accuracy  
- Falls back to **Haversine distance** for large datasets  

---

### 🔵 3. Clustering (Multi-Vehicle Distribution)

- Uses **KMeans clustering** to divide delivery locations into groups (one per vehicle)  
- Each cluster represents the **set of stops assigned to a vehicle**  

#### 🧠 Key Idea:
- Minimizes intra-cluster distance → nearby deliveries are grouped together  
- Ensures **balanced load distribution across vehicles**  

#### ⚙️ Advanced Clustering Techniques:
- **Constraint-aware weighting:**  
  - Perishable deliveries are **pulled closer to the depot**  
  - Ensures they are delivered earlier in the route  

- **Dynamic clustering options:**
  - **DBSCAN (auto-tuned)** for density-based grouping  
  - **Agglomerative clustering** as fallback  
  - **Sweep algorithm** (angle + distance hybrid) for geometric efficiency  

---

### 🚚 4. Route Optimization (Per Vehicle)

- **≤ 8 stops:**  
  - Brute-force permutations → **globally optimal route**

- **> 8 stops:**  
  - Start with **Nearest Neighbor (priority-aware)**  
  - Improve using **2-opt optimization**  
  - Apply **priority scoring**:
    - Perishable items → early delivery  
    - Time-window violations → penalty  

---

### 📈 5. Visualization & Metrics

- Generates **interactive route map (Folium)**  
- Displays:
  - Vehicle-wise routes  
  - Stop sequence  
  - Delivery clusters  

- Provides analytics:
  - Total distance  
  - Fuel usage  
  - CO₂ emissions  
  - Eco-efficiency score  

## 📊 Impact at a Glance
 
<div align="center">
 
| Metric | Without Optimizer | With Optimizer | Improvement |
|--------|:-----------------:|:--------------:|:-----------:|
| Route Distance | Baseline (naive NN) | Heuristic VRP | **↓ 20–30%** |
| Delivery Order | Sequential | Priority-scored | **Perishables first** |
| Vehicle Load | Unbalanced | KMeans clustered | **±Balanced** |
| CO₂ Emissions | Untracked | Calculated per km | **Full visibility** |
| Geocoding Failures | Silent | Logged + skipped | **Zero crashes** |
 
</div>
 
<br/>

## 💻 Tech Stack
 
<div align="center">
 
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11, Flask | Web server & routing engine |
| **Optimization** | NumPy, SciPy, itertools | VRP heuristics & 2-opt |
| **ML / Clustering** | scikit-learn | KMeans, DBSCAN, Agglomerative |
| **Routing API** | OpenRouteService | Real road-network distances & geocoding |
| **Geocoding Fallback** | Nominatim (OSM) | Zero-cost fallback geocoder |
| **Mapping** | Folium + HeatMap plugin | Interactive layered route map |
| **PDF Export** | ReportLab | Driver-ready route sheets |
| **Data Handling** | pandas | CSV validation & transformation |
| **Env Config** | python-dotenv | Secure API key management |
| **Logging** | Python logging | Structured file + console output |
 
</div>
 
<br/>

## ⚙️ Installation
 
### Prerequisites
 
- Python 3.11+
- [OpenRouteService API key](https://openrouteservice.org/dev/#/signup) (free tier available)
 
### Setup
 
```bash
# 1. Clone the repository
git clone https://github.com/yourusername/delivery-route-optimizer.git
cd delivery-route-optimizer
 
# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
 
# 3. Install dependencies
pip install -r requirements.txt
 
# 4. Configure environment variables
cp .env.example .env
# → Add your ORS_API_KEY to .env
 
# 5. Run the app
python app.py
# → Open http://localhost:8000
```
 
### Environment Variables
 
```env
ORS_API_KEY=your_openrouteservice_api_key_here
```
 
<br/>

## 🚀 Usage
 
### Via Web Interface
 
1. Enter your **starting warehouse / depot address**
2. Add delivery addresses — mark each as `perishable` or `standard`
3. Set the **number of vehicles**
4. Click **"Optimize Route"**
5. Explore the **interactive map**, review per-vehicle stop sequences, and export a **PDF route sheet**
 
### Via CSV Bulk Upload
 
Upload a `.csv` file with the following format:
 
```csv
address,item_type
"Madhapur, Hyderabad","perishable"
"Jubilee Hills, Hyderabad","non-perishable"
"Somajiguda, Hyderabad","perishable"
```
 
> `item_type` is optional — defaults to `non-perishable` if omitted.
 
<br/>

## 🌍 Real-World Use Cases
 
| Industry | Use Case | Key Benefit |
|----------|----------|-------------|
| 🛒 **Grocery / Q-Commerce** | BigBasket, Blinkit-style last-mile | Perishables delivered first, zero spoilage |
| 💊 **Pharma / Cold Chain** | Vaccine & medicine distribution | Time-window enforcement, route PDF for compliance |
| 📦 **E-Commerce** | Flipkart / Amazon last-mile | Multi-vehicle load balancing, CO₂ reporting |
| 🍱 **Corporate Catering** | Multi-campus meal delivery | Tight time windows, optimized clustering |
| 🌱 **Green Logistics** | Eco-delivery startups | Carbon tracking, distance minimization |
 
<br/>

## **Roles & How They Use the Delivery Route Optimizer**

### **1️⃣ Logistics / Delivery Manager**

**Role:** Planning & Oversight (No Travel)

**How they use it:**

- Logs into the dashboard and enters the **starting warehouse location**.
- Adds all delivery addresses and marks items as **perishable or standard**.
- Selects the **number of vehicles** available.
- Clicks **“Optimize Route”** to generate **vehicle-wise optimized routes**.
- Receives:
    - Optimized stop sequences for each vehicle
    - Estimated distance per vehicle
    - Fuel usage and **carbon emission metrics**
    - Perishable items highlighted for priority
- Can **export routes** for drivers and ensure all deliveries are efficiently assigned.

**Example:**

A BigBasket manager plans 30 deliveries, marking milk, fruits, and vegetables as perishable, and assigns 4 vans. The system clusters stops using **KMeans**, prioritizes perishables via **priority-based scoring**, and improves routes using **2-Opt and heuristic algorithms**. The manager reviews and shares the planned routes—no travel required.

---

### **2️⃣ Operations / Dispatch Team**

**Role:** Pre-Delivery Route Management

**How they use it:**

- Reviews **vehicle-wise planned routes** generated by the system.
- Checks **stop sequence**, ensuring **perishable items** are scheduled early.
- Ensures **balanced load distribution** across vehicles.
- Can make **manual adjustments** before deliveries start.

**Example:**

Dispatcher notices Vehicle 2 has several perishable deliveries in the second half of its route. They adjust the sequence to ensure perishables reach customers first, optimizing efficiency and minimizing spoilage.

---

### **3️⃣ Fleet / Vehicle Drivers**

**Role:** Route Execution

**How they use it:**

- Receives the **planned route** from the manager or dispatcher.
- Follows the **stop sequence** as per the optimized plan.
- Delivers items in order, with **perishables prioritized**.

**Example:**

Driver 1 starts at the warehouse, delivers milk and vegetables first, then continues with standard items. The route minimizes total travel distance and ensures freshness.

---

### **4️⃣ Business / Sustainability Analysts**

**Role:** Post-Planning Efficiency Review

**How they use it:**

- Analyzes **optimized routes** for efficiency metrics.
- Compares **optimized vs naive distance** to calculate savings.
- Evaluates **carbon emissions, fuel usage, and eco-efficiency score**.

**Example:**

Analyst reports that the system reduced total delivery distance by 15%, saved fuel, and decreased CO₂ emissions, providing actionable insights for future route planning.

---
## 📈 Performance Characteristics
 
| Scenario | Algorithm | Typical Runtime |
|----------|-----------|-----------------|
| 1 vehicle, ≤8 stops | Brute-force permutation | < 1s |
| 1 vehicle, >8 stops | Priority-NN + 2-opt | < 2s |
| 5 vehicles, 50 stops | KMeans + 2-opt + cross-swap | 3–8s |
| 5 vehicles, 150 stops (CSV max) | Haversine fallback + heuristic | 5–12s |
 
> API call savings: Geocoding cache eliminates duplicate calls; distance matrix cache eliminates re-computation on unchanged inputs.
 
<br/>

## 🌱 Sustainability Impact

| Metric | Value |
| --- | --- |
| Total Distance | Calculated automatically |
| Estimated Fuel | L |
| CO₂ Emission | kg |
| Eco Efficiency Score | % |

> Every optimized route reduces distance and emissions compared to naive sequential routing.
> 

---

## 🤝 Contributing
 
Contributions are welcome and appreciated!
 
```bash
# Fork → Clone → Branch → Commit → PR
git checkout -b feature/your-feature-name
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
```
<br/>

---
<div align="center">
Built with 🧠 algorithms and 🌿 sustainability in mind
 </div>
<br/>
