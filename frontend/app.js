const API_BASE_URL = "http://localhost:8000/api";

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    if (!localStorage.getItem('adminToken')) {
        window.location.href = '/login.html';
        return;
    }
    
    // Set email in settings modal
    try {
        const token = localStorage.getItem('adminToken');
        const payload = JSON.parse(atob(token.split('.')[1]));
        const emailEl = document.getElementById('settings-email');
        if (emailEl) emailEl.innerText = payload.sub;
    } catch(e) {}
    
    fetchStats();
    fetchPatients();
    setupUpload();
});

// Tab Switching Logic
function switchTab(tabId) {
    document.querySelectorAll('.sidebar nav a').forEach(a => {
        if(a.id === 'nav-dashboard' || a.id === 'nav-patients') {
            a.classList.remove('active');
        }
    });
    const targetNav = document.getElementById(`nav-${tabId}`);
    if(targetNav) targetNav.classList.add('active');
    
    document.querySelectorAll('.view-section').forEach(section => {
        section.classList.remove('active');
    });
    const targetView = document.getElementById(`${tabId}-view`);
    if(targetView) targetView.classList.add('active');
}

let riskChartInstance = null;
let pipelineChartInstance = null;

function renderCharts(data) {
    const riskCtx = document.getElementById('riskChart');
    if (riskCtx) {
        if (riskChartInstance) riskChartInstance.destroy();
        riskChartInstance = new Chart(riskCtx, {
            type: 'doughnut',
            data: {
                labels: ['Potential Gap', 'Review Required', 'Supported'],
                datasets: [{
                    data: [data.high_risk || 0, data.medium_risk || 0, data.low_risk || 0],
                    backgroundColor: ['#ee5d50', '#ffab00', '#01b574'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                },
                cutout: '70%'
            }
        });
    }

    const pipelineCtx = document.getElementById('pipelineChart');
    if (pipelineCtx) {
        if (pipelineChartInstance) pipelineChartInstance.destroy();
        pipelineChartInstance = new Chart(pipelineCtx, {
            type: 'bar',
            data: {
                labels: ['Patients', 'Docs Processed'],
                datasets: [{
                    label: 'Count',
                    data: [data.total_patients || 0, data.documents_processed || 0],
                    backgroundColor: ['#4318ff', '#00b5ad'],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
}

function getAuthHeaders() {
    return {
        'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
    };
}

function handleAuthError(response) {
    if (response.status === 401) {
        localStorage.removeItem('adminToken');
        window.location.href = '/login.html';
        return true;
    }
    return false;
}

function logout() {
    localStorage.removeItem('adminToken');
    window.location.href = '/login.html';
}

// Fetch Overview Stats
async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`, { headers: getAuthHeaders() });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            const data = await response.json();
            document.getElementById('stat-total').innerText = data.total_patients.toLocaleString();
            document.getElementById('stat-reviewed').innerText = data.patients_reviewed.toLocaleString();
            if(document.getElementById('stat-docs')) {
                document.getElementById('stat-docs').innerText = (data.documents_processed || 0).toLocaleString();
            }
            document.getElementById('stat-high-risk').innerText = data.high_risk.toLocaleString();
            if(document.getElementById('stat-medium-risk')) {
                document.getElementById('stat-medium-risk').innerText = data.medium_risk.toLocaleString();
            }
            document.getElementById('stat-low-risk').innerText = data.low_risk.toLocaleString();
            
            // Render Charts
            renderCharts(data);
        } else {
            console.error("Failed to fetch stats");
        }
    } catch (error) {
        console.error("Error connecting to API:", error);
    }
}

// Global state for patients
window.allPatients = [];

// Fetch Patients Table
async function fetchPatients() {
    try {
        const response = await fetch(`${API_BASE_URL}/patients`, { headers: getAuthHeaders() });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            let data = await response.json();
            
            // Priority Sorting: High Risk first
            const riskWeight = {
                "Potential Documentation Gap": 3,
                "Review Required": 2,
                "Supported Documentation": 1
            };
            
            data.sort((a, b) => {
                const wA = riskWeight[a.risk_level] || 0;
                const wB = riskWeight[b.risk_level] || 0;
                return wB - wA;
            });
            
            window.allPatients = data;
            renderPatients(window.allPatients);
        }
    } catch (error) {
        console.error("Error fetching patients:", error);
    }
}

// Render Patients Table
function renderPatients(patients) {
    const tbody = document.querySelector('#patients-table tbody');
    tbody.innerHTML = '';
    
    if (patients.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td colspan="7" style="text-align: center; padding: 60px 20px; color: var(--text-secondary);">
                <i class="ph ph-magnifying-glass" style="font-size: 48px; color: var(--border-color); margin-bottom: 16px; display: inline-block;"></i>
                <h3 style="color: var(--text-primary); margin-bottom: 8px; font-size: 18px;">No patients found</h3>
                <p style="font-size: 14px;">Try adjusting your filters or search criteria.</p>
            </td>
        `;
        tbody.appendChild(tr);
        return;
    }
    
    patients.forEach(p => {
        const tr = document.createElement('tr');
        
        let riskClass = 'low';
        if (p.risk_level === 'Potential Documentation Gap') {
            riskClass = 'high';
        } else if (p.risk_level === 'Review Required') {
            riskClass = 'medium';
        }
        
        let statusBadge = p.review_status === 'Completed' 
            ? `<span class="badge" style="background-color: var(--success-color); color: white; margin-left: 8px;"><i class="ph ph-check-circle"></i> Completed</span>` 
            : '';
        
        tr.innerHTML = `
            <td>${p.patient_id}</td>
            <td>${p.age || 'N/A'}</td>
            <td>${p.gender || 'N/A'}</td>
            <td>${p.prediction_class}</td>
            <td>${(p.probability * 100).toFixed(1)}%</td>
            <td><span class="badge ${riskClass}">${p.risk_level}</span>${statusBadge}</td>
            <td>
                <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="viewPatient('${p.patient_id}')">
                    Review
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Filter Patients
function filterPatients() {
    const riskFilter = document.getElementById('risk-filter').value;
    const searchFilter = document.getElementById('patient-search').value.toLowerCase();
    const genderFilter = document.getElementById('gender-filter').value;
    
    const filtered = window.allPatients.filter(p => {
        let matchesRisk = false;
        
        if (riskFilter === 'All') {
            matchesRisk = true;
        } else if (riskFilter === 'Review Completed') {
            matchesRisk = (p.review_status === 'Completed');
        } else {
            // When filtering by a specific risk level, only show items that haven't been completed yet
            matchesRisk = (p.risk_level === riskFilter && p.review_status !== 'Completed');
        }
        
        const matchesSearch = !searchFilter || (p.patient_id && p.patient_id.toLowerCase().includes(searchFilter));
        const matchesGender = genderFilter === 'All' || (p.gender && p.gender === genderFilter);
        
        return matchesRisk && matchesSearch && matchesGender;
    });
    
    // Store currently filtered view for bulk download
    window.currentFilteredPatients = filtered;
    
    renderPatients(filtered);
}

// Download Bulk Report
async function downloadBulkReport() {
    if (!window.currentFilteredPatients || window.currentFilteredPatients.length === 0) {
        alert("No patients in the current view to generate a report.");
        return;
    }
    
    const patientIds = window.currentFilteredPatients.map(p => p.patient_id);
    
    try {
        const response = await fetch(`${API_BASE_URL}/report/bulk`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ patient_ids: patientIds })
        });
        
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `HCC_Filtered_Summary_Report.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        } else {
            alert('Failed to generate bulk report.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Connection error.');
    }
}

// Using marked.js instead for robust markdown parsing

// Open Explanation Modal
async function viewPatient(patientId) {
    const modal = document.getElementById('explanation-modal');
    modal.classList.add('active');
    
    document.getElementById('review-patient-id').innerText = patientId;
    document.getElementById('review-prediction').innerText = 'Loading...';
    document.getElementById('review-probability').innerText = '...';
    document.getElementById('review-risk').innerText = '...';
    document.getElementById('review-completeness').innerText = '...';
    document.getElementById('review-explanation').innerHTML = '<p><i class="ph ph-spinner ph-spin"></i> Analyzing evidence and generating explanation...</p>';
    document.getElementById('review-records').innerHTML = '<ul><li>Loading records...</li></ul>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/patient/${patientId}`, { headers: getAuthHeaders() });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            const data = await response.json();
            
            document.getElementById('review-prediction').innerText = data.prediction?.prediction_class || 'N/A';
            document.getElementById('review-probability').innerText = data.prediction ? `${(data.prediction.probability * 100).toFixed(1)}%` : 'N/A';
            
            const riskLevel = data.prediction?.risk_level || 'N/A';
            const riskSpan = document.getElementById('review-risk');
            riskSpan.innerText = riskLevel;
            riskSpan.className = `badge ${riskLevel === 'Potential Documentation Gap' ? 'high' : riskLevel === 'Review Required' ? 'medium' : 'low'}`;
            
            const markBtn = document.getElementById('btn-mark-review');
            const completeBtn = document.getElementById('btn-mark-completed');
            if (markBtn) markBtn.style.display = 'inline-block';
            if (completeBtn) {
                if (data.prediction && data.prediction.review_status === 'Completed') {
                    completeBtn.style.display = 'none';
                    if (markBtn) markBtn.style.display = 'none';
                } else {
                    completeBtn.style.display = 'inline-block';
                }
            }
            
            // Format markdown for the explanation using marked.js
            document.getElementById('review-explanation').innerHTML = typeof marked !== 'undefined' ? marked.parse(data.explanation || "") : data.explanation;
            
            // Populate Patient Records and calculate completeness
            let conditions = data.patient?.conditions || [];
            let medications = data.patient?.medications || [];
            
            let recordsHtml = '<ul>';
            
            if (conditions.length > 0) {
                recordsHtml += '<li><strong>Conditions:</strong><ul>';
                conditions.forEach(c => {
                    recordsHtml += `<li>${c.DESCRIPTION || c.CODE || 'Unknown Condition'} (Date: ${c.START || 'Unknown'})</li>`;
                });
                recordsHtml += '</ul></li>';
            } else {
                recordsHtml += '<li><strong>Conditions:</strong> None found.</li>';
            }
            
            if (medications.length > 0) {
                recordsHtml += '<li><strong>Medications:</strong><ul>';
                medications.forEach(m => {
                    recordsHtml += `<li>${m.DESCRIPTION || m.CODE || 'Unknown Medication'} (Date: ${m.START || 'Unknown'})</li>`;
                });
                recordsHtml += '</ul></li>';
            } else {
                recordsHtml += '<li><strong>Medications:</strong> None found.</li>';
            }
            
            recordsHtml += '</ul>';
            document.getElementById('review-records').innerHTML = recordsHtml;
            
            // Calculate a heuristic completeness percentage based on documents found
            let expectedDocs = 5; // Expected some mix of conditions and meds
            let foundDocs = conditions.length + medications.length;
            let completeness = Math.min(100, Math.round((foundDocs / expectedDocs) * 100));
            document.getElementById('review-completeness').innerText = `${completeness}%`;
            
        } else {
            document.getElementById('review-explanation').innerText = "Error loading patient details.";
            document.getElementById('review-records').innerHTML = '<ul><li>Error loading records.</li></ul>';
        }
    } catch (error) {
        document.getElementById('review-explanation').innerText = "Error connecting to server.";
        document.getElementById('review-records').innerHTML = '<ul><li>Error connecting to server.</li></ul>';
    }
}

// Regenerate AI Explanation
async function regenerateExplanation(event) {
    const patientId = document.getElementById('review-patient-id').innerText;
    if (!patientId) return;
    
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Regenerating...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/patient/${patientId}/regenerate-explanation`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            const data = await response.json();
            document.getElementById('review-explanation').innerHTML = typeof marked !== 'undefined' ? marked.parse(data.explanation || "") : data.explanation;
        } else {
            alert('Failed to regenerate explanation.');
        }
    } catch (error) {
        console.error("Error regenerating explanation:", error);
        alert('Connection error.');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Setup Drag & Drop Upload
function setupUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    
    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.backgroundColor = 'rgba(67, 24, 255, 0.08)';
    });
    
    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.backgroundColor = 'rgba(67, 24, 255, 0.02)';
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.backgroundColor = 'rgba(67, 24, 255, 0.02)';
        
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateDropZoneText(fileInput.files[0].name);
        }
    });
    
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            updateDropZoneText(fileInput.files[0].name);
        }
    });
    
    function updateDropZoneText(filename) {
        dropZone.innerHTML = `
            <i class="ph ph-file-zip" style="font-size: 48px; color: var(--primary-color);"></i>
            <h3 style="margin-top: 16px;">${filename}</h3>
            <p style="color: var(--success-color); margin-top: 8px;">Ready to process</p>
        `;
    }
    
    uploadBtn.addEventListener('click', async () => {
        if (fileInput.files.length === 0) {
            alert('Please select a ZIP file first.');
            return;
        }
        
        const file = fileInput.files[0];
        if (!file.name.endsWith('.zip')) {
            alert('Only ZIP files are supported.');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        uploadBtn.innerText = 'Processing...';
        uploadBtn.disabled = true;
        
        try {
            const response = await fetch(`${API_BASE_URL}/upload-zip`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: formData
            });
            if (handleAuthError(response)) return;
            
            if (response.ok) {
                alert('File uploaded successfully! Processing will begin in the background.');
                document.getElementById('upload-modal').classList.remove('active');
                // Refresh data after a delay to simulate processing
                setTimeout(() => {
                    fetchStats();
                    fetchPatients();
                }, 2000);
            } else {
                alert('Error uploading file.');
            }
        } catch (error) {
            console.error('Upload error:', error);
            alert('Connection error during upload.');
        } finally {
            uploadBtn.innerText = 'Process Data';
            uploadBtn.disabled = false;
        }
    });
}

// Generate PDF Report
async function downloadReport() {
    const patientId = document.getElementById('review-patient-id').innerText;
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Generating...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/patient/${patientId}/report`, {
            headers: getAuthHeaders()
        });
        
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `HCC_Patient_Report_${patientId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        } else {
            alert("Failed to generate PDF report.");
        }
    } catch (e) {
        console.error("Error downloading report:", e);
        alert("Connection error while generating report.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Mark as Review Required
async function markReviewRequired() {
    const patientId = document.getElementById('review-patient-id').innerText;
    try {
        const response = await fetch(`${API_BASE_URL}/patient/${patientId}/mark-review-required`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            document.getElementById('explanation-modal').classList.remove('active');
            fetchStats();
            fetchPatients();
        } else {
            alert('Failed to update status.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Connection error.');
    }
}

// Mark as Review Completed
async function markReviewCompleted() {
    const patientId = document.getElementById('review-patient-id').innerText;
    try {
        const response = await fetch(`${API_BASE_URL}/patient/${patientId}/mark-review-completed`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        if (handleAuthError(response)) return;
        
        if (response.ok) {
            document.getElementById('explanation-modal').classList.remove('active');
            fetchStats();
            fetchPatients();
        } else {
            alert('Failed to mark as completed.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Connection error.');
    }
}

// Sort Table
let currentSort = { column: null, ascending: true };
window.sortTable = function(column) {
    if (currentSort.column === column) {
        currentSort.ascending = !currentSort.ascending;
    } else {
        currentSort.column = column;
        currentSort.ascending = true;
    }
    
    window.allPatients.sort((a, b) => {
        let valA, valB;
        if (column === 'id') {
            valA = a.patient_id || "";
            valB = b.patient_id || "";
        } else if (column === 'age') {
            valA = a.age || 0;
            valB = b.age || 0;
        } else if (column === 'gender') {
            valA = a.gender || "";
            valB = b.gender || "";
        } else if (column === 'probability') {
            valA = a.probability || 0;
            valB = b.probability || 0;
        }
        
        if (valA < valB) return currentSort.ascending ? -1 : 1;
        if (valA > valB) return currentSort.ascending ? 1 : -1;
        return 0;
    });
    
    filterPatients();
};
