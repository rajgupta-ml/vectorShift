import { useEffect, useState } from 'react';
import axios from 'axios';
import DataTable from './item-card';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'Hubspot': 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState([]);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            const response = await axios.post(`http://localhost:8000/integrations/${endpoint}/load`, formData);
            const data = response.data;
            setLoadedData(data);
        } catch (e) {
            alert(e?.response?.data?.detail);
        }
    }

    useEffect(() => {
        console.log(loadedData)
    }, [loadedData])

    return (
        <div className="container">
            <div className="content">
                <div className="header">
                    <h1>Integration Data Viewer</h1>
                    <p>View and manage your integration data</p>
                </div>

                <div className="button-group">
                    <button onClick={handleLoad} className="button button-primary">
                        Load Demo Data
                    </button>
                    <button onClick={() => setLoadedData([])} className="button button-secondary">
                        Clear Data
                    </button>
                </div>

                {loadedData.length > 0 ? (
                    <DataTable data={loadedData} />
                ) : (
                    <div className="empty-state">
                        <p>No data loaded. Click "Load Demo Data" to see an example.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
