<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('delivery_plans', function (Blueprint $table) {
            $table->id();
            $table->foreignId('current_room_id')->nullable()->constrained('rooms')->nullOnDelete();
            $table->enum('status', ['active', 'completed'])->default('active');
            $table->json('sequence')->comment('Ordered array of order IDs');
            $table->json('estimated_times')->nullable()->comment('Estimated times per order');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('delivery_plans');
    }
};
