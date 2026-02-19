interface HeaderProps {
    // Future: could add navigation props if needed
}

export default function Header({ }: HeaderProps) {
    return (
        <header className="bg-white shadow-sm px-4 py-2 sticky top-0 z-50">
            <a href="/" className="flex items-center text-gray-900 no-underline">
                <img src="/logo.png" alt="AmIAire" className="h-10 mr-2" />
            </a>
        </header>
    );
}
