import React from 'react';
import { Cpu, ChevronDown } from 'lucide-react';

export default function MachineSelector({
  machines = [],
  selectedMachineId,
  onSelectMachine,
  disabled = false
}) {
  const currentMachine = machines.find((m) => String(m.id) === String(selectedMachineId));

  return (
    <div className="card card-industrial p-3 bg-white mb-3">
      <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
        <div className="d-flex align-items-center gap-2">
          <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
            <Cpu size={22} />
          </div>
          <div>
            <div className="text-muted small fw-semibold text-uppercase" style={{ fontSize: '0.68rem', letterSpacing: '0.05em' }}>
              Target Machine Context
            </div>
            <div className="fw-bold text-dark" style={{ fontSize: '1rem' }}>
              {currentMachine ? currentMachine.name : 'Select a machine to query'}
            </div>
          </div>
        </div>

        <div className="d-flex align-items-center gap-2">
          <select
            className="form-select form-select-sm"
            style={{ minWidth: '220px' }}
            value={selectedMachineId || ''}
            onChange={(e) => onSelectMachine(e.target.value)}
            disabled={disabled}
            aria-label="Select Machine"
          >
            <option value="">-- Choose Machine --</option>
            {machines.map((machine) => (
              <option key={machine.id} value={machine.id}>
                {machine.name} ({machine.machine_code || machine.model_number || 'Standard'})
              </option>
            ))}
          </select>

          {currentMachine && (
            <span className="badge bg-light text-secondary border d-none d-lg-inline-block small">
              {currentMachine.manuals_count || 0} Manuals Indexed
            </span>
          )}
        </div>
      </div>

      {currentMachine && currentMachine.description && (
        <div className="mt-2 pt-2 border-top text-muted small" style={{ fontSize: '0.78rem' }}>
          <strong>Specs:</strong> {currentMachine.description}
        </div>
      )}
    </div>
  );
}
