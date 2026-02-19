interface LoadingSpinnerProps {
    isLoading: boolean;
}

export default function LoadingSpinner({ isLoading }: LoadingSpinnerProps) {
    if (!isLoading) return null;

    return (
        <div className="fixed top-0 left-0 w-full h-full bg-white bg-opacity-75 flex justify-center items-center z-[1050] backdrop-blur-sm">
            <div className="w-16 h-16 border-4 border-ami-azul-claro border-t-transparent rounded-full animate-spin"></div>
        </div>
    );
}
