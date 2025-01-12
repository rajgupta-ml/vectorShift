import { useState, useEffect } from 'react';
import {
    Box,
    Button,
    CircularProgress
} from '@mui/material';
import axios from 'axios';

export const HubSpotIntegration = ({
    user,
    org,
    integrationParams,
    setIntegrationParams
}) => {
    const [isConnected, setIsConnected] = useState(false)
    const [isConnecting, setIsConnecting] = useState(false)

    // Function to open OAuth in a new window
    const handleConnectClick = async () => {
        try {
            setIsConnecting(true)
            const formData = new FormData()
            formData.append('user_id', user)
            formData.append('org_id', org)
            const response = await axios.post(`http://localhost:8000/integrations/hubspot/authorize`, formData)
            const authURL = response?.data

            const newWindow = window.open(authURL, 'HubSpot Authorization', 'width=600, height=600')

            // Polling for the window to close
            const pollTimer = window.setInterval(() => {
                if (newWindow?.closed !== false) {
                    window.clearInterval(pollTimer)
                    handleWindowClosed()
                }
            }, 200)
        } catch (e) {
            setIsConnecting(false)
            alert(e?.response?.data?.detail)
        }
    }

    // Function to handle logic when the OAuth window closes
    const handleWindowClosed = async () => {
        try {
            const formData = new FormData()
            formData.append('user_id', user)
            formData.append('org_id', org)
            const response = await axios.post(`http://localhost:8000/integrations/hubspot/credentials`, formData)
            const credentials = response.data
            if (credentials) {
                setIsConnecting(false)
                setIsConnected(true)
                setIntegrationParams(prev => ({ ...prev, credentials: credentials, type: 'Hubspot' }))
            }
            setIsConnecting(false)
        } catch (e) {
            setIsConnecting(false)
            alert(e?.response?.data?.detail)
        }
    }

    useEffect(() => {
        setIsConnected(integrationParams?.credentials ? true : false)
    }, [integrationParams])

    return (
        <Box className="mt-4">
            <h3 className="text-lg font-semibold mb-2">Parameters</h3>
            <Box className="flex items-center justify-center mt-4">
                <Button
                    variant={isConnected ? 'outline' : 'default'}
                    onClick={isConnected ? () => { } : handleConnectClick}
                    disabled={isConnecting}
                    className={`
            ${isConnected ? 'bg-green-500 hover:bg-green-600 text-white' : ''}
            ${isConnected ? 'pointer-events-none cursor-default' : ''}
          `}
                >
                    {isConnected ? 'HubSpot Connected' : isConnecting ? <CircularProgress size={20} /> : 'Connect to HubSpot'}
                </Button>
            </Box>
        </Box>
    )
}


