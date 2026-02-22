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

## 🚀 Key Features

### 1️⃣ Smart Route Optimization

- **Balanced multi-vehicle routing** using heuristic VRP.
- Supports **perishable vs. standard items** for priority scheduling.
- Integrates **time window penalties** to ensure on-time deliveries.

### 2️⃣ Dynamic Clustering & Load Balancing

- Automatic delivery clustering using **KMeans** for multiple vehicles.
- Minimizes distance differences between vehicles to optimize load distribution.

### 3️⃣ Real-Time Map & Visualization

- Interactive **Folium map** showing all routes with vehicle-specific colors.
- Markers indicate **depot, stops, and optimized sequence**.

### 4️⃣ Sustainable Logistics Dashboard

- Calculates **fuel consumption**, **CO₂ emission**, and **eco-efficiency score**.
- Helps businesses track environmental impact of deliveries.

### 5️⃣ Easy-to-Use Web Interface

- Enter **starting point** (supports GPS auto-detection).
- Add **multiple delivery addresses** with type selection (perishable/standard).
- Configure **number of vehicles**.
- One-click **Optimize Route** button with full route summary and metrics.

---

## 📊 How It Works

1. **Geocoding:** Converts addresses into coordinates using **OpenRouteService** and fallback to **Nominatim**.
2. **Distance Matrix:** Calculates distances between all points using **ORS distance matrix API**.
3. **Multi-Vehicle Distribution:** Uses **KMeans clustering** to assign stops to different vehicles for balanced load.
4. **Route Optimization per Vehicle:**
    - **≤8 stops:** Brute-force permutations to find the **absolute optimal sequence**.
    - **>8 stops:**
        - Start with **Nearest Neighbor Heuristic with Priority**.
        - Refine using **2-opt improvement**.
        - Apply **priority-based scoring** for perishables and time windows.
5. **Visualization & Metrics:** Generates interactive **map**, route summary, and **eco-efficiency dashboard**.

---

## 💻 Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| Routing & Optimization | OpenRouteService API, NumPy, SciPy |
| Frontend | HTML5, CSS3, JavaScript |
| Mapping & Visualization | Folium |
| Machine Learning | scikit-learn (KMeans) |
| Environment Variables | python-dotenv |

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

## 📈 Optimization Results

- **Distance Reduction:** Saves up to 20–30% distance over naive routing.
- **Perishable Prioritization:** Ensures high-priority deliveries are early in the route.
- **Balanced Load:** Minimizes difference between longest and shortest vehicle routes.

---

## 📌 Real-World Use Cases

1. **Grocery & Food Delivery Services**
    - Prioritize perishable items like fruits, vegetables, and dairy to be delivered first.
    - Example: A company like **BigBasket** or **Zomato** can reduce spoilage and fuel costs while ensuring timely deliveries.
2. **Pharmaceutical & Medical Supplies**
    - Ensure time-sensitive medicines and vaccines reach hospitals or pharmacies within strict time windows.
    - Example: Cold-chain vaccine distribution in urban and semi-urban areas.
3. **E-Commerce & Logistics Companies**
    - Optimize multi-vehicle routes for multiple warehouses and high-volume deliveries.
    - Example: **Flipkart or Amazon** can cut delivery distances and balance driver workloads while reducing CO₂ emissions.
4. **Corporate & Event Catering**
    - Deliver prepared meals or perishable catering items to multiple locations efficiently.
    - Example: Large corporate campuses with several office buildings needing coordinated deliveries.
5. **Sustainable Urban Delivery Initiatives**
    - Municipal services or eco-friendly startups can plan routes to reduce fuel consumption and environmental footprint.
    - Example: City-based delivery startups promoting **green logistics**.

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

### **Key Note on Monitoring:**

- **Current scope:** Pre-delivery monitoring and planning.
- Managers and dispatchers **monitor routes, perishable priorities, and efficiency metrics before deliveries start**.
- **Live GPS tracking is a future enhancement**, not implemented in this version.

## 🌟 Future Enhancements

- Real-time **traffic & weather integration**.
- **Dynamic rerouting** based on delivery delays.
- **Mobile-friendly interface**.
- **Machine learning prediction** for estimated delivery times.
