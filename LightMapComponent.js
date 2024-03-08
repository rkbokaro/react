import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

function LightMapComponent() {
  const [junctionData, setJunctionData] = useState([]);
  const [plotMarkers, setPlotMarkers] = useState(false);
  const [plotLines, setPlotLines] = useState(false);
  const [filterValue, setFilterValue] = useState('KR');
  const [dataLoaded, setDataLoaded] = useState(false);
  const [stationData, setStationData] = useState([]);
  const [plotStationMarkers, setPlotStationMarkers] = useState(false);
  const mapRef = useRef(null);
  const stationMarkersRef = useRef([]); // Reference for station markers

  useEffect(() => {
    if (!mapRef.current) {
      const newMap = L.map('map').setView([20.5937, 78.9629], 5);
      mapRef.current = newMap;

      const bhuvanLayer = L.tileLayer.wms('https://bhuvan-vec1.nrsc.gov.in/bhuvan/gwc/service/wms/', {
        layers: 'india3',
        format: 'image/png',
        transparent: true,
        attribution: '&copy; Bhuvan Map - <a href="https://bhuvan.nrsc.gov.in/">Bhuvan</a>',
      }).addTo(newMap);

      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (plotMarkers) {
      const filteredJunctions = filterJunctions(junctionData);
      filteredJunctions.forEach((junction) => {
        if (isValidLatLng(junction.node1Latitude, junction.node1Longitude)) {
          const circle = L.circle([junction.node1Latitude, junction.node1Longitude], {
            color: 'red',
            fillColor: 'red',
            fillOpacity: 0.5,
            radius: 100,
          }).addTo(mapRef.current);

          circle.bindPopup(`Junction ID: ${junction.junctionId}`);
        }
      });
    } else {
      mapRef.current.eachLayer((layer) => {
        if (layer instanceof L.Circle) {
          mapRef.current.removeLayer(layer);
        }
      });
    }
  }, [plotMarkers, junctionData]);

  useEffect(() => {
    if (plotLines) {
      const filteredJunctions = filterJunctions(junctionData);
      filteredJunctions.forEach((junction) => {
        if (
          isValidLatLng(junction.node1Latitude, junction.node1Longitude) &&
          isValidLatLng(junction.node2Latitude, junction.node2Longitude)
        ) {
          const line = L.polyline(
            [
              [junction.node1Latitude, junction.node1Longitude],
              [junction.node2Latitude, junction.node2Longitude],
            ],
            { color: 'blue' }
          )
            .addTo(mapRef.current)
            .on('click', () => handlePolylineClick(junction)); // Add click event
          line.bindPopup(`Junction ID: ${junction.junctionId}`);
        }
      });
    } else {
      mapRef.current.eachLayer((layer) => {
        if (layer instanceof L.Polyline) {
          mapRef.current.removeLayer(layer);
        }
      });
    }
  }, [plotLines, junctionData]);

  useEffect(() => {
    if (plotStationMarkers) {
      const filteredStations = filterStations(stationData);
      filteredStations.forEach((station) => {
        if (isValidLatLng(station.sttnLatitude, station.sttnLongitude)) {
          const stationMarker = L.marker([station.sttnLatitude, station.sttnLongitude]).addTo(mapRef.current);
          stationMarker.bindPopup(`Station ID: ${station.stationId}`);
          // Add the station marker to a reference array for potential removal later
          stationMarkersRef.current.push(stationMarker);
        }
      });
    } else {
      // Use the same logic to remove station markers as done for circles and polylines
      mapRef.current.eachLayer((layer) => {
        if (layer instanceof L.Marker && layer.options.icon.options.className === 'leaflet-div-icon') {
          mapRef.current.removeLayer(layer);
        }
      });
      // Clear the reference array
      stationMarkersRef.current = [];
    }
  }, [plotStationMarkers, stationData]);

  const isValidLatLng = (latitude, longitude) => {
    return latitude !== undefined && longitude !== undefined && latitude !== 0 && longitude !== 0;
  };

  const filterJunctions = (junctions) => {
    return junctions.filter(
      (junction) =>
        junction &&
        junction.node1DvsnCode &&
        isValidLatLng(junction.node1Latitude, junction.node1Longitude) &&
        isValidLatLng(junction.node2Latitude, junction.node2Longitude) &&
        junction.node1DvsnCode.toLowerCase().includes(filterValue.toLowerCase())
    );
  };

  const filterStations = (stations) => {
    return stations.filter(
      (station) =>
        station &&
        station.dvsnCode &&
        isValidLatLng(station.sttnLatitude, station.sttnLongitude) &&
        station.dvsnCode.toLowerCase().includes(filterValue.toLowerCase())
    );
  };

  const handlePolylineClick = async (junction) => {
    // Clear any existing selection
    clearSelection();

    // Find stations between two nodes
    const node1Code = junction.node1Code;
    const node2Code = junction.node2Code;

    const matchingStation = stationData.filter(
      (station) => station.node1Code === node1Code && station.node2Code === node2Code
    );

    // Plot markers for matching stations
    matchingStation.forEach((station) => {
      if (isValidLatLng(station.sttnLatitude, station.sttnLongitude)) {
        const stationMarker = L.marker([station.sttnLatitude, station.sttnLongitude]).addTo(mapRef.current);
        stationMarker.bindPopup(`Station ID: ${station.stationId}`);
        // Add the station marker to a reference array for potential removal later
        stationMarkersRef.current.push(stationMarker);
      }
    });

    // Do something with matchingStation, e.g., update state
    console.log('Matching Stations:', matchingStation);
  };

  const clearSelection = () => {
    // Clear any existing selection logic goes here

    // Remove existing station markers
    stationMarkersRef.current.forEach((marker) => {
      mapRef.current.removeLayer(marker);
    });
    stationMarkersRef.current = [];
  };

  const fetchData = async () => {
    try {
      const junctionResponse = await fetch('http://localhost:8082/junctionLink');
      const rawJunctionData = await junctionResponse.json();
      setJunctionData(rawJunctionData);

      const stationResponse = await fetch('http://localhost:8082/internalNode');
      const stationData = await stationResponse.json();
      setStationData(stationData);

      setDataLoaded(true); // Mark data as loaded
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  return (
    <div>
      <input
        type="text"
        placeholder="Filter by node1DvsnCode"
        value={filterValue}
        onChange={(e) => setFilterValue(e.target.value)}
        disabled={!dataLoaded}
      />
      <button onClick={() => setPlotMarkers(!plotMarkers)} disabled={!dataLoaded}>
        {plotMarkers ? 'Hide Markers' : 'Show Markers'}
      </button>
      <button onClick={() => setPlotLines(!plotLines)} disabled={!dataLoaded}>
        {plotLines ? 'Hide Lines' : 'Show Lines'}
      </button>
      <button onClick={() => setPlotStationMarkers(!plotStationMarkers)} disabled={!dataLoaded}>
        {plotStationMarkers ? 'Hide Stations' : 'Show Stations'}
      </button>
      <button onClick={() => fetchData()} disabled={!dataLoaded}>
        Filter
      </button>
      <div id="map" style={{ height: '70vh', width: '100%' }}></div>
    </div>
  );
}

export default LightMapComponent;
