# RAILETA – Dynamic Train ETA Forecasting System

RAILETA is a real-time train tracking and ETA forecasting system designed for Indian Railways.

The system uses live train information to display:

- Current train location
- Current running speed
- Last stopped station
- Next stopping station
- Current delay
- Station-wise journey information
- Scheduled arrival and departure
- Actual arrival and departure
- Estimated arrival and departure for upcoming stations
- Dynamic ETA
- Train route visualization
- Live railway map
- Weather information

## Problem

Traditional train schedules provide fixed arrival times and do not continuously reflect the actual movement of a train.

RAILETA aims to provide a dynamic view of a train's journey by using live operational information and continuously updating ETA information.

## Features

### Train Search
Search trains between two railway stations.

### Live Train Tracking
View the current position and operational status of a train.

### Dynamic ETA
Display station-wise estimated arrival and departure times.

### Delay Analysis
Show current delay and progressively adjusted future delay.

### Journey Timeline
Display the complete route with:

- Scheduled Arrival
- Actual Arrival
- Scheduled Departure
- Actual Departure
- Estimated Arrival
- Estimated Departure
- Distance
- Platform information

### Interactive Railway Map
Display the selected train route and other live trains on an interactive map.

### Weather
Display weather information for the train's current location.

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Leaflet
- React Leaflet
- Lucide React

### Backend
- Python
- FastAPI
- Uvicorn

### Data
- RailRadar live train data
- Local Indian railway station dataset

## Project Architecture

User
↓
React Frontend
↓
FastAPI Backend
↓
Railway Data APIs
↓
Live Train Data
↓
ETA / Delay Processing
↓
Frontend Dashboard

## Running the Project

### Backend

```bash
cd BACKEND
pip install -r requirements.txt
uvicorn main:app --reload
