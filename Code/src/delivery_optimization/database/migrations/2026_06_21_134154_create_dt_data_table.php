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
        Schema::create('dt_data', function (Blueprint $table) {
            $table->id();
            $table->string('salle_code_depart')->nullable();
            $table->string('salle_code_arrivee')->nullable();
            $table->dateTime('date_depart')->nullable();
            $table->dateTime('date_arrivee')->nullable();
            $table->foreignId('order_id')->nullable()->constrained('orders')->nullOnDelete();
            $table->unsignedSmallInteger('duree')->comment('Duration in seconds')->nullable();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('dt_data');
    }
};
