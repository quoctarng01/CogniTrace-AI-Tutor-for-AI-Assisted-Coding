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
    expect(xEl.closest('[class*="variable"]')).toHaveClass('changed');
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
    expect(screen.getByText(/no variables/i)).toBeInTheDocument();
  });
});
