"use client";

import ActionHeader from "@/components/common/ActionHeader";
import { CreateItemModal } from "@/components/items/CreateItem";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

interface ItemsListHeaderProps {
  onSearch?: (query: string) => void;
  title?: string;
  initialSearchQuery?: string;
  description?: string;
}

export function ItemsListHeader({
  onSearch,
  title = "Items",
  description = "Manage your items",
}: Readonly<ItemsListHeaderProps>) {
  const searchParams = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") ?? "");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const handleSearch = () => {
    if (onSearch) {
      onSearch(searchQuery);
    }
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    if (onSearch) {
      onSearch("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  return (
    <div className="space-y-4 mb-3">
      <ActionHeader
        title={title}
        description={description}
        onSeachQuery={setSearchQuery}
        searchQuery={searchQuery}
        onKeyDown={handleKeyDown}
        onClearSearch={handleClearSearch}
        onSetModalOpen={setIsCreateModalOpen}
      />

      {/* Create Item Modal */}
      <CreateItemModal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} />
    </div>
  );
}
