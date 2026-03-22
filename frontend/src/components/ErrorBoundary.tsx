import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
    children: ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    message: string;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, message: '' };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, message: error?.message || 'Unknown frontend error' };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('Frontend runtime error:', error, info);
    }

    handleReload = () => {
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-ami-gris p-6">
                    <div className="max-w-3xl mx-auto bg-white rounded-lg shadow p-6">
                        <h1 className="text-xl font-semibold text-red-700 mb-3">Error en el frontend</h1>
                        <p className="text-gray-700 mb-3">
                            La aplicación lanzó un error en tiempo de ejecución y por eso veías pantalla en blanco.
                        </p>
                        <pre className="bg-gray-100 rounded p-3 text-sm overflow-x-auto mb-4">
                            {this.state.message}
                        </pre>
                        <button
                            type="button"
                            onClick={this.handleReload}
                            className="px-4 py-2 rounded bg-ami-azul text-white"
                        >
                            Recargar
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
