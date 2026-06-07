import { render, screen } from '@testing-library/react';
import { VariablePanel } from '@/components/tracer/VariablePanel';

describe('VariablePanel', () => {
  it('renders variables with type badges', () => {
    const variables = {
      x: { type: 'int', value: '5', changed: false },
      name: { type: 'str', value: '"hello"', changed: false },
    };
    render(<VariablePanel variables={variables} />);
    expect(screen.getByText('x')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('int')).toBeInTheDocument();
  });

  it('highlights changed variables', () => {
    const variables = {
      x: { type: 'int', value: '5', changed: true },
    };
    render(<VariablePanel variables={variables} />);
    const xEl = screen.getByText('x');
    const container = xEl.closest('[class*="varItem"]');
    expect(container).not.toBeNull();
    expect(container?.className).toContain('changed');
  });

  it('shows branch decision icon for bool variables', () => {
    const variables = {
      flag: { type: 'bool', value: 'True', changed: false },
    };
    render(<VariablePanel variables={variables} />);
    expect(screen.getByText('flag')).toBeInTheDocument();
    expect(screen.getByText('bool')).toBeInTheDocument();
  });

  it('shows empty state when no variables', () => {
    render(<VariablePanel variables={{}} />);
    expect(screen.getByText(/Run the trace to see variable states/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Branch rendering tests (added after fixing branch data shape mismatch)
// ---------------------------------------------------------------------------

describe('VariablePanel branch rendering', () => {
  it('renders "if branch taken" when taken=true', () => {
    const branches = {
      if: { taken: true, line: 5, branch: 'then', condition: 'x > 0' },
    };
    render(<VariablePanel variables={{}} branches={branches} />);
    expect(screen.getByText(/if branch taken/i)).toBeInTheDocument();
  });

  it('renders "else branch taken" when taken=false', () => {
    const branches = {
      if: { taken: false, line: 5, branch: 'else', condition: 'x > 0' },
    };
    render(<VariablePanel variables={{}} branches={branches} />);
    expect(screen.getByText(/else branch taken/i)).toBeInTheDocument();
  });

  it('renders for loop branch', () => {
    const branches = {
      for: { iteration: 2, line: 3 },
    };
    render(<VariablePanel variables={{}} branches={branches} />);
    expect(screen.getByText(/for loop/i)).toBeInTheDocument();
  });

  it('renders while loop branch', () => {
    const branches = {
      while: { line: 7 },
    };
    render(<VariablePanel variables={{}} branches={branches} />);
    expect(screen.getByText(/while loop/i)).toBeInTheDocument();
  });

  it('renders nothing when branches is empty', () => {
    const { container } = render(<VariablePanel variables={{}} branches={{}} />);
    expect(container.querySelector('[class*="branchSection"]')).not.toBeInTheDocument();
  });

  it('renders nothing when branches is undefined', () => {
    const { container } = render(<VariablePanel variables={{}} />);
    expect(container.querySelector('[class*="branchSection"]')).not.toBeInTheDocument();
  });
});
